"""
Betfair API Client for GB Track Specialist Production Trial

Handles authentication and core API operations for Betfair Exchange.
Adapted from 02_Upset_Prediction/02_Production/betfair_client.py
"""

import requests
import json
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import time
import logging
from pathlib import Path
import os
import base64
import tempfile

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BetfairClient:
    """
    Client for interacting with Betfair Exchange API.
    
    Handles:
    - Authentication with SSL certificates
    - Session management
    - Account operations
    - Market data retrieval
    - Rate limiting
    """
    
    # Betfair API endpoints
    LOGIN_URL = "https://identitysso-cert.betfair.com/api/certlogin"
    BETTING_URL = "https://api.betfair.com/exchange/betting/json-rpc/v1"
    ACCOUNT_URL = "https://api.betfair.com/exchange/account/json-rpc/v1"
    
    def __init__(self, username: str = None, password: str = None, 
                 app_key: str = None, cert_path: str = None, key_path: str = None):
        """
        Initialize Betfair client.
        
        Args:
            username: Betfair username (or set BETFAIR_USERNAME env var)
            password: Betfair password (or set BETFAIR_PASSWORD env var)
            app_key: Betfair application key (or set BETFAIR_APP_KEY env var)
            cert_path: Path to SSL certificate (or set BETFAIR_CERT_PATH env var)
            key_path: Path to SSL private key (or set BETFAIR_KEY_PATH env var)
        """
        # Load credentials from environment or parameters
        self.username = username or os.getenv('BETFAIR_USERNAME')
        self.password = password or os.getenv('BETFAIR_PASSWORD')
        self.app_key = app_key or os.getenv('BETFAIR_APP_KEY')
        
        # Handle certificates: base64 (Railway) or file paths (local)
        self.cert_path, self.key_path = self._setup_certificates(cert_path, key_path)
        
        # Validate credentials
        if not all([self.username, self.password, self.app_key]):
            raise ValueError(
                "Missing credentials. Set BETFAIR_USERNAME, BETFAIR_PASSWORD, "
                "BETFAIR_APP_KEY environment variables or pass as parameters"
            )
        
        # Validate certificate files exist
        if not Path(self.cert_path).exists():
            raise FileNotFoundError(
                f"Certificate file not found: {self.cert_path}\n"
                "Ensure certificates are properly configured"
            )
        if not Path(self.key_path).exists():
            raise FileNotFoundError(
                f"Private key file not found: {self.key_path}\n"
                "Ensure certificates are properly configured"
            )
        
        self.session_token = None
        self.request_count = 0
        self.last_request_time = 0
        
        # Rate limiting: Max 20 requests per second
        self.min_request_interval = 0.05  # 50ms between requests
        
        logger.info("Betfair client initialized for GB Track Specialist")
    
    def _setup_certificates(self, cert_path: str = None, key_path: str = None) -> tuple:
        """
        Set up SSL certificates for Betfair authentication.
        
        Supports two modes:
        1. Base64 encoded certificates (for Railway deployment)
        2. File path certificates (for local development)
        
        Args:
            cert_path: Optional path to certificate file
            key_path: Optional path to private key file
            
        Returns:
            Tuple of (cert_path, key_path)
        """
        # Check for base64 encoded certificates (Railway deployment)
        cert_base64 = os.getenv('BETFAIR_CERT_BASE64')
        key_base64 = os.getenv('BETFAIR_KEY_BASE64')
        
        if cert_base64 and key_base64:
            logger.info("Using base64 encoded certificates (Railway deployment)")
            
            # Create temp directory for certificates
            temp_dir = Path(tempfile.gettempdir()) / 'betfair_certs'
            temp_dir.mkdir(exist_ok=True)
            
            # Decode and write certificates
            cert_file = temp_dir / 'client-2048.crt'
            key_file = temp_dir / 'client-2048.key'
            
            try:
                cert_file.write_bytes(base64.b64decode(cert_base64))
                key_file.write_bytes(base64.b64decode(key_base64))
                
                # Set appropriate permissions (read-only for owner)
                cert_file.chmod(0o600)
                key_file.chmod(0o600)
                
                logger.info(f"✓ Certificates decoded successfully")
                return str(cert_file), str(key_file)
                
            except Exception as e:
                raise ValueError(f"Failed to decode base64 certificates: {str(e)}")
        
        # Otherwise, use file paths
        if cert_path:
            final_cert_path = cert_path
        elif os.getenv('BETFAIR_CERT_PATH'):
            final_cert_path = os.getenv('BETFAIR_CERT_PATH')
        else:
            # Look for certs in current directory or certs subdirectory
            current_dir = Path(__file__).parent
            possible_paths = [
                current_dir / 'certs' / 'client-2048.crt',
                current_dir / 'client-2048.crt',
                Path.cwd() / 'certs' / 'client-2048.crt'
            ]
            final_cert_path = None
            for path in possible_paths:
                if path.exists():
                    final_cert_path = str(path)
                    break
            if not final_cert_path:
                # If no file found, use env var path (will error later if not found)
                final_cert_path = str(possible_paths[0])
        
        if key_path:
            final_key_path = key_path
        elif os.getenv('BETFAIR_KEY_PATH'):
            final_key_path = os.getenv('BETFAIR_KEY_PATH')
        else:
            current_dir = Path(__file__).parent
            possible_paths = [
                current_dir / 'certs' / 'client-2048.key',
                current_dir / 'client-2048.key',
                Path.cwd() / 'certs' / 'client-2048.key'
            ]
            final_key_path = None
            for path in possible_paths:
                if path.exists():
                    final_key_path = str(path)
                    break
            if not final_key_path:
                final_key_path = str(possible_paths[0])
        
        logger.info(f"Using certificate files from disk")
        return final_cert_path, final_key_path
    
    def login(self) -> bool:
        """
        Authenticate with Betfair and obtain session token.
        
        Returns:
            True if login successful, False otherwise
        """
        try:
            logger.info("Logging in to Betfair...")
            
            headers = {
                'X-Application': self.app_key,
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            
            payload = {
                'username': self.username,
                'password': self.password
            }
            
            response = requests.post(
                self.LOGIN_URL,
                data=payload,
                headers=headers,
                cert=(self.cert_path, self.key_path),
                timeout=30
            )
            
            if response.status_code == 200:
                resp_json = response.json()
                
                if resp_json.get('loginStatus') == 'SUCCESS':
                    self.session_token = resp_json.get('sessionToken')
                    logger.info("✓ Login successful")
                    return True
                else:
                    error = resp_json.get('loginStatus', 'Unknown error')
                    logger.error(f"Login failed: {error}")
                    return False
            else:
                logger.error(f"Login request failed: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Login error: {str(e)}")
            return False
    
    def _enforce_rate_limit(self):
        """Enforce rate limiting between requests."""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.min_request_interval:
            time.sleep(self.min_request_interval - time_since_last)
        
        self.last_request_time = time.time()
        self.request_count += 1
    
    def _make_api_request(self, endpoint: str, method: str, 
                          params: Dict = None, retry_on_session_error: bool = True) -> Optional[Dict]:
        """
        Make a JSON-RPC API request to Betfair.
        
        Args:
            endpoint: API endpoint URL
            method: API method name
            params: Method parameters
            retry_on_session_error: If True, attempt re-login on session error
            
        Returns:
            API response or None if error
        """
        if not self.session_token:
            logger.error("Not logged in. Call login() first.")
            return None
        
        self._enforce_rate_limit()
        
        headers = {
            'X-Application': self.app_key,
            'X-Authentication': self.session_token,
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        payload = {
            'jsonrpc': '2.0',
            'method': method,
            'params': params or {},
            'id': self.request_count
        }
        
        try:
            response = requests.post(
                endpoint,
                data=json.dumps(payload),
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                resp_json = response.json()
                
                if 'result' in resp_json:
                    return resp_json['result']
                elif 'error' in resp_json:
                    error = resp_json['error']
                    
                    # Check for session expiration error
                    error_code = error.get('data', {}).get('APINGException', {}).get('errorCode', '')
                    if error_code == 'INVALID_SESSION_INFORMATION' and retry_on_session_error:
                        logger.warning("Session expired, attempting to re-login...")
                        if self.login():
                            logger.info("✓ Re-login successful, retrying request...")
                            return self._make_api_request(endpoint, method, params, retry_on_session_error=False)
                        else:
                            logger.error("Re-login failed")
                            return None
                    
                    logger.error(f"API error: {error}")
                    return None
                else:
                    logger.error(f"Unexpected response: {resp_json}")
                    return None
            else:
                logger.error(f"API request failed: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"API request error: {str(e)}")
            return None
    
    def get_upcoming_greyhound_races(self, hours_ahead: float = 24, 
                                     country_codes: List[str] = None) -> List[Dict]:
        """
        Get upcoming greyhound races (GB only by default).
        
        Args:
            hours_ahead: How many hours ahead to look
            country_codes: Optional list of country codes (default: ['GB'])
            
        Returns:
            List of race information dictionaries
        """
        # Default to GB races only for this system
        if country_codes is None:
            country_codes = ['GB']
        
        # Get greyhound event type ID
        event_types = self._make_api_request(
            self.BETTING_URL,
            'SportsAPING/v1.0/listEventTypes',
            params={'filter': {}}
        )
        
        if not event_types:
            return []
        
        greyhound_id = None
        for event_type in event_types:
            if 'Greyhound' in event_type['eventType']['name']:
                greyhound_id = event_type['eventType']['id']
                break
        
        if not greyhound_id:
            logger.warning("Greyhound racing event type not found")
            return []
        
        # Build time filter
        now = datetime.utcnow()
        to_time = now + timedelta(hours=hours_ahead)
        
        time_filter = {
            'from': now.strftime('%Y-%m-%dT%H:%M:%SZ'),
            'to': to_time.strftime('%Y-%m-%dT%H:%M:%SZ')
        }
        
        # Build market filter
        market_filter = {
            'eventTypeIds': [greyhound_id],
            'marketTypeCodes': ['WIN'],  # Win market
            'marketStartTime': time_filter,
            'marketCountries': country_codes
        }
        
        # Get market catalogue
        result = self._make_api_request(
            self.BETTING_URL,
            'SportsAPING/v1.0/listMarketCatalogue',
            params={
                'filter': market_filter,
                'maxResults': 1000,
                'marketProjection': [
                    'COMPETITION',
                    'EVENT',
                    'EVENT_TYPE',
                    'MARKET_START_TIME',
                    'RUNNER_DESCRIPTION',
                    'RUNNER_METADATA'
                ]
            }
        )
        
        if not result:
            return []
        
        # Parse races
        races = []
        for market in result:
            race_info = {
                'market_id': market['marketId'],
                'market_name': market['marketName'],
                'event_name': market['event']['name'],
                'venue': market['event']['venue'],
                'country_code': market['event'].get('countryCode', 'Unknown'),
                'race_time': market['marketStartTime'],
                'num_runners': len(market.get('runners', []))
            }
            races.append(race_info)
        
        logger.info(f"Found {len(races)} upcoming GB greyhound races")
        return races
    
    def get_market_book(self, market_ids: List[str]) -> Optional[List[Dict]]:
        """Get current market prices and status."""
        price_projection = {
            'priceData': ['EX_BEST_OFFERS', 'SP_AVAILABLE', 'SP_TRADED'],
            'virtualise': True
        }
        
        result = self._make_api_request(
            self.BETTING_URL,
            'SportsAPING/v1.0/listMarketBook',
            params={
                'marketIds': market_ids,
                'priceProjection': price_projection
            }
        )
        
        return result
    
    def logout(self):
        """Logout and invalidate session token."""
        if self.session_token:
            try:
                headers = {
                    'X-Application': self.app_key,
                    'X-Authentication': self.session_token
                }
                
                requests.post(
                    "https://identitysso.betfair.com/api/logout",
                    headers=headers,
                    timeout=10
                )
                
                logger.info("Logged out from Betfair")
            except Exception as e:
                logger.error(f"Logout error: {str(e)}")
            
            self.session_token = None

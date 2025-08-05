# server.py
from flask import Flask, json, jsonify, request
import requests
from datetime import date
import os
from functools import wraps
from dotenv import load_dotenv
import logging
import random
import time
import json as json_module

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

app = Flask(__name__)

API_SECRET_KEY = os.getenv('API_SECRET_KEY')

def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        if not API_SECRET_KEY:
            logger.error("API_SECRET_KEY environment variable is not set")
            return jsonify({
                "error": True,
                "status": 500,
                "body": "Server configuration error"
            }), 500
        if not api_key or api_key != API_SECRET_KEY:
            return jsonify({
                "error": True,
                "status": 401,
                "body": "Invalid or missing API key"
            }), 401
        return f(*args, **kwargs)
    return decorated_function

# Enhanced browser headers to avoid detection
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9,en-GB;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Referer": "https://www.sofascore.com/",
    "Origin": "https://www.sofascore.com",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "DNT": "1",
    "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"'
}

enum_status_code = {
   'notstarted' : "Not Started" ,
   'inprogress' : "In Progress" ,
   'finished' : "Finished" 
}

enum_score_type = {
    '1' : 'Home',
    '2' : 'Away',
    '3' : 'Draw'
}

@app.route("/live", methods=["GET"])
@require_api_key
def live():
    try:
        sportCategory = request.args.get("sportCategory")
        if not sportCategory:
            return jsonify({
                "error": True,
                "status": 400,
                "body": "Sport category is required"
            }), 400

        session = requests.Session()
        
        # Set up session with enhanced headers
        session.headers.update(BROWSER_HEADERS)
        
        # Add some randomization to appear more human-like
        session.headers.update({
            "X-Requested-With": "XMLHttpRequest",
            "X-Forwarded-For": f"{random.randint(1, 255)}.{random.randint(1, 255)}.{random.randint(1, 255)}.{random.randint(1, 255)}"
        })

        # First, visit the main page to establish session
        logger.info("Visiting main page to establish session...")
        main_page_resp = session.get("https://www.sofascore.com/", timeout=30)
        logger.info(f"Main page response: {main_page_resp.status_code}")
        
        # Add a small delay to mimic human behavior
        time.sleep(1)
        
        # Now make the API request
        url = f"https://www.sofascore.com/api/v1/sport/{sportCategory}/scheduled-events/{get_today_date_formatted()}"
        logger.info(f"Making request to: {url}")
        
        # Add query parameters that might help
        params = {
            "_": int(time.time() * 1000),  # Timestamp
            "v": "1"  # Version parameter
        }
        
        resp = session.get(url, params=params, timeout=30)
        logger.info(f"API Response status: {resp.status_code}")
        logger.info(f"API Response headers: {dict(resp.headers)}")
        
        if resp.status_code == 403:
            logger.error("Received 403 Forbidden - likely bot detection")
            return jsonify({
                "error": True,
                "status": 403,
                "body": "Access forbidden - SofaScore is blocking serverless requests. Try using a different approach or check if the API endpoint has changed."
            }), 403
        
        if resp.status_code != 200:
            return jsonify({
                "error": True,
                "status": resp.status_code,
                "body": f"External API error: {resp.text}"
            }), resp.status_code

        data = resp.json()
        
        # Validate response structure
        if 'events' not in data:
            return jsonify({
                "error": True,
                "status": 500,
                "body": "Invalid response structure from external API"
            }), 500

        results = {} 
        number_of_events = len(data['events'])
        results['numberOfEvents'] = number_of_events 
        results['events'] = []
        finished_events = 0 
        inprogress_events = 0 
        notstarted_events = 0 
        
        logger.info(f"Processing {number_of_events} events")
        
        for event in data['events']:
            try:
                # Safely access nested dictionary keys
                status_type = event.get('status', {}).get('type', 'unknown')
                
                if status_type == 'finished':
                    finished_events += 1 
                elif status_type == 'inprogress':
                    inprogress_events += 1 
                elif status_type == 'notstarted':
                    notstarted_events += 1 
                
                # Safely access team information
                home_team = event.get('homeTeam', {})
                away_team = event.get('awayTeam', {})
                home_score = event.get('homeScore', {})
                away_score = event.get('awayScore', {})
                
                event_data = {
                    'id': event.get('id'),
                    'homeTeam': home_team.get('name', 'Unknown'),
                    'homeTeamId': home_team.get('id'),
                    'awayTeam': away_team.get('name', 'Unknown'),
                    'awayTeamId': away_team.get('id'),
                    'homeScore': home_score.get('current', '-') if status_type != 'notstarted' else '-',
                    'awayScore': away_score.get('current', '-') if status_type != 'notstarted' else '-',
                    'live': status_type == 'inprogress',
                    'result': enum_score_type.get(str(event.get('winnerCode')), '-') if status_type == 'finished' else '-',
                    'time': event.get('time'),
                    'status': event.get('status')
                }
                results['events'].append(event_data)
                
            except Exception as e:
                logger.error(f"Error processing event: {e}")
                continue
                
        results['finishedEvents'] = finished_events 
        results['inprogressEvents'] = inprogress_events 
        results['notstartedEvents'] = notstarted_events 
        
        return jsonify(results)
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error: {e}")
        return jsonify({
            "error": True,
            "status": 500,
            "body": f"Network error: {str(e)}"
        }), 500
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return jsonify({
            "error": True,
            "status": 500,
            "body": f"Internal server error: {str(e)}"
        }), 500

@app.route("/live-alt", methods=["GET"])
@require_api_key
def live_alternative():
    """
    Alternative approach that tries to bypass bot detection using different strategies
    """
    try:
        sportCategory = request.args.get("sportCategory")
        if not sportCategory:
            return jsonify({
                "error": True,
                "status": 400,
                "body": "Sport category is required"
            }), 400

        # Try different User-Agent strings
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ]
        
        session = requests.Session()
        
        # Use a random User-Agent
        headers = BROWSER_HEADERS.copy()
        headers["User-Agent"] = random.choice(user_agents)
        headers.update({
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        })
        
        session.headers.update(headers)
        
        # Try to get the main page first
        logger.info("Alternative approach: Visiting main page...")
        main_resp = session.get("https://www.sofascore.com/", timeout=30)
        
        if main_resp.status_code != 200:
            logger.error(f"Main page failed: {main_resp.status_code}")
            return jsonify({
                "error": True,
                "status": main_resp.status_code,
                "body": "Failed to access main page"
            }), main_resp.status_code
        
        # Try a different API endpoint format
        url = f"https://www.sofascore.com/api/v1/sport/{sportCategory}/scheduled-events/{get_today_date_formatted()}"
        
        # Add more realistic parameters
        params = {
            "_": int(time.time() * 1000),
            "v": "1",
            "t": str(int(time.time())),
            "r": str(random.randint(1000, 9999))
        }
        
        logger.info(f"Alternative approach: Making request to {url}")
        resp = session.get(url, params=params, timeout=30)
        
        if resp.status_code == 403:
            return jsonify({
                "error": True,
                "status": 403,
                "body": "SofaScore is blocking all serverless requests. Consider using a different data source or implementing a proxy solution."
            }), 403
        
        if resp.status_code != 200:
            return jsonify({
                "error": True,
                "status": resp.status_code,
                "body": f"Alternative approach failed: {resp.text}"
            }), resp.status_code
        
        # Process the response the same way
        data = resp.json()
        
        if 'events' not in data:
            return jsonify({
                "error": True,
                "status": 500,
                "body": "Invalid response structure"
            }), 500
        
        # Return the same processed data
        results = {
            "numberOfEvents": len(data['events']),
            "events": [],
            "finishedEvents": 0,
            "inprogressEvents": 0,
            "notstartedEvents": 0
        }
        
        for event in data['events']:
            try:
                status_type = event.get('status', {}).get('type', 'unknown')
                
                if status_type == 'finished':
                    results['finishedEvents'] += 1
                elif status_type == 'inprogress':
                    results['inprogressEvents'] += 1
                elif status_type == 'notstarted':
                    results['notstartedEvents'] += 1
                
                home_team = event.get('homeTeam', {})
                away_team = event.get('awayTeam', {})
                home_score = event.get('homeScore', {})
                away_score = event.get('awayScore', {})
                
                event_data = {
                    'id': event.get('id'),
                    'homeTeam': home_team.get('name', 'Unknown'),
                    'homeTeamId': home_team.get('id'),
                    'awayTeam': away_team.get('name', 'Unknown'),
                    'awayTeamId': away_team.get('id'),
                    'homeScore': home_score.get('current', '-') if status_type != 'notstarted' else '-',
                    'awayScore': away_score.get('current', '-') if status_type != 'notstarted' else '-',
                    'live': status_type == 'inprogress',
                    'result': enum_score_type.get(str(event.get('winnerCode')), '-') if status_type == 'finished' else '-',
                    'time': event.get('time'),
                    'status': event.get('status')
                }
                results['events'].append(event_data)
                
            except Exception as e:
                logger.error(f"Error processing event: {e}")
                continue
        
        return jsonify(results)
        
    except Exception as e:
        logger.error(f"Alternative approach error: {e}")
        return jsonify({
            "error": True,
            "status": 500,
            "body": f"Alternative approach failed: {str(e)}"
        }), 500

def get_today_date_formatted():
    return date.today().strftime("%Y-%m-%d")

# Add a health check endpoint
@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "healthy",
        "message": "Server is running"
    })

@app.route("/test-sofascore", methods=["GET"])
@require_api_key
def test_sofascore():
    """
    Test endpoint to check if we can access SofaScore at all
    """
    try:
        session = requests.Session()
        session.headers.update(BROWSER_HEADERS)
        
        # Test 1: Try to access main page
        logger.info("Testing main page access...")
        main_resp = session.get("https://www.sofascore.com/", timeout=30)
        
        # Test 2: Try a simple API endpoint
        logger.info("Testing API access...")
        test_url = "https://www.sofascore.com/api/v1/sport/football/scheduled-events/2024-01-01"
        api_resp = session.get(test_url, timeout=30)
        
        return jsonify({
            "main_page_status": main_resp.status_code,
            "main_page_headers": dict(main_resp.headers),
            "api_status": api_resp.status_code,
            "api_headers": dict(api_resp.headers),
            "api_response_preview": api_resp.text[:500] if api_resp.status_code == 200 else api_resp.text,
            "user_agent": session.headers.get("User-Agent")
        })
        
    except Exception as e:
        logger.error(f"Test error: {e}")
        return jsonify({
            "error": True,
            "status": 500,
            "body": f"Test failed: {str(e)}"
        }), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))

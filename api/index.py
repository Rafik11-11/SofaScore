# server.py
from flask import Flask, json, jsonify, request
import requests
from datetime import date
import os
from functools import wraps
from dotenv import load_dotenv
import logging

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

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Referer": "https://www.sofascore.com/",
    "Origin": "https://www.sofascore.com"
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
        session.headers.update(BROWSER_HEADERS)

        # Get the main page first
        session.get("https://www.sofascore.com/")

        url = f"https://www.sofascore.com/api/v1/sport/{sportCategory}/scheduled-events/{get_today_date_formatted()}"
        logger.info(f"Making request to: {url}")
        
        resp = session.get(url, timeout=30)
        logger.info(f"Response status: {resp.status_code}")
        
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

def get_today_date_formatted():
    return date.today().strftime("%Y-%m-%d")

# Add a health check endpoint
@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "healthy",
        "message": "Server is running"
    })

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))

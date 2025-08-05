# server.py
from flask import Flask, json, jsonify, request
import requests
from datetime import date
import os
from functools import wraps
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)


API_SECRET_KEY = os.getenv('API_SECRET_KEY')

def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
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
    sportCategory = request.args.get("sportCategory")
    if not sportCategory:
        return jsonify({
            "error": True,
            "status": 400,
            "body": "Sport category is required"
        }), 400

    
    session = requests.Session()
    session.headers.update(BROWSER_HEADERS)

    
    session.get("https://www.sofascore.com/")

    url = f"https://www.sofascore.com/api/v1/sport/{sportCategory}/scheduled-events/{get_today_date_formatted()}"
    resp = session.get(url)
    data = resp.json() 
    results = {} 
    number_of_events = len(data['events'])
    results['numberOfEvents'] = number_of_events 
    results['events'] = []
    finished_events = 0 
    inprogress_events = 0 
    notstarted_events = 0 
    print(data['events'])
    for event in data['events']:
        if event['status']['type'] == 'finished':
            finished_events += 1 
        elif event['status']['type'] == 'inprogress':
            inprogress_events += 1 
        elif event['status']['type'] == 'notstarted':
            notstarted_events += 1 
        results['events'].append({
                'id': event['id'],
                'homeTeam': event['homeTeam']['name'],
                'homeTeamId': event['homeTeam']['id'],
                'awayTeam': event['awayTeam']['name'],
                'awayTeamId': event['awayTeam']['id'],
                'homeScore': event['homeScore']['current'] if event['status']['type'] != 'notstarted' else '-',
                'awayScore': event['awayScore']['current'] if event['status']['type'] != 'notstarted' else '-',
                'live': event['status']['type'] == 'inprogress',
                'result': enum_score_type[str(event['winnerCode'])] if event['status']['type'] == 'finished' else '-',
                'time': event['time'] ,
                'status': event['status']
            })       
    results['finishedEvents'] = finished_events 
    results['inprogressEvents'] = inprogress_events 
    results['notstartedEvents'] = notstarted_events 
    if resp.status_code == 200:
        return jsonify(results)
    else:
        return jsonify({
            "error": True,
            "status": resp.status_code,
            "body": resp.text
        }), resp.status_code



def get_today_date_formatted():
    return date.today().strftime("%Y-%m-%d")

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))

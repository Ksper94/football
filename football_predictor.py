import streamlit as st
import requests
import datetime
from datetime import date

# Clés API
API_KEY = 'aa14874600855457b5a838ec894a06ae'
WEATHER_API_KEY = 'mOpwoft03br5cj7z'

# URLs de base pour l'API Football
API_URL_LEAGUES = 'https://v3.football.api-sports.io/leagues'
API_URL_FIXTURES = 'https://v3.football.api-sports.io/fixtures'
API_URL_TEAMS = 'https://v3.football.api-sports.io/teams'
API_URL_STANDINGS = 'https://v3.football.api-sports.io/standings'
API_URL_ODDS = 'https://v3.football.api-sports.io/odds'

# URL météo (Meteoblue)
API_URL_WEATHER = 'https://my.meteoblue.com/packages/basic-1h'

# Headers pour l'API football
headers = {
    'x-apisports-key': API_KEY,
    'x-apisports-host': 'v3.football.api-sports.io'
}

st.title("Calcul de probabilités pour les matchs de football à venir")

# Sélection de la date
today = date.today()
selected_date = st.date_input("Sélectionnez une date (à partir d'aujourd'hui):", min_value=today, value=today)

# Continents (exemple statique)
continents = ["Europe", "South America", "North America", "Asia", "Africa"]
selected_continent = st.selectbox("Sélectionnez un continent :", continents)

if selected_continent:
    response = requests.get(API_URL_LEAGUES, headers=headers)
    if response.status_code == 200:
        data_leagues = response.json().get('response', [])
        all_countries = list(set([league['country']['name'] for league in data_leagues if 'country' in league and league['country']['name'] is not None]))
        all_countries.sort()
        selected_country = st.selectbox("Sélectionnez un pays :", all_countries)
    else:
        st.error("Impossible de récupérer la liste des ligues.")
        selected_country = None
else:
    selected_country = None

if selected_country:
    # Filtrer les ligues par pays
    leagues_in_country = [league for league in data_leagues if league['country']['name'] == selected_country]
    league_names = [l['league']['name'] for l in leagues_in_country]
    league_names.sort()
    selected_league_name = st.selectbox("Sélectionnez une compétition :", league_names)

    # Récupérer l'ID de la ligue
    selected_league = next((l for l in leagues_in_country if l['league']['name'] == selected_league_name), None)
    if selected_league:
        league_id = selected_league['league']['id']
    else:
        league_id = None
else:
    league_id = None

if league_id:
    params_fixtures = {
        'league': league_id,
        'season': datetime.datetime.now().year,
        'date': selected_date.strftime('%Y-%m-%d')
    }
    response_fixtures = requests.get(API_URL_FIXTURES, headers=headers, params=params_fixtures)
    if response_fixtures.status_code == 200:
        data_fixtures = response_fixtures.json().get('response', [])
        match_list = []
        for fix in data_fixtures:
            home_team = fix['teams']['home']['name']
            away_team = fix['teams']['away']['name']
            fixture_id = fix['fixture']['id']
            match_str = f"{home_team} vs {away_team}"
            match_list.append((match_str, fixture_id))
        
        if match_list:
            selected_match = st.selectbox("Sélectionnez un match :", [m[0] for m in match_list])
            match_id = next((m[1] for m in match_list if m[0] == selected_match), None)
        else:
            st.info("Aucun match trouvé pour la date et la compétition sélectionnées.")
            match_id = None
    else:
        st.error("Impossible de récupérer les matchs.")
        match_id = None
else:
    match_id = None

def get_team_form(team_id, n=5):
    # Forme sur les n derniers matchs
    form_params = {
        'team': team_id,
        'last': n
    }
    form_resp = requests.get(API_URL_FIXTURES, headers=headers, params=form_params)
    if form_resp.status_code == 200:
        form_data = form_resp.json().get('response', [])
        wins, draws, losses = 0, 0, 0
        for m in form_data:
            home_goals = m['goals']['home']
            away_goals = m['goals']['away']
            home_id = m['teams']['home']['id']
            away_id = m['teams']['away']['id']
            if home_id == team_id:
                if home_goals > away_goals:
                    wins += 1
                elif home_goals == away_goals:
                    draws += 1
                else:
                    losses += 1
            else:
                if away_goals > home_goals:
                    wins += 1
                elif away_goals == home_goals:
                    draws += 1
                else:
                    losses += 1
        total = wins + draws + losses
        if total > 0:
            form_score = wins/total  # ratio de victoires
        else:
            form_score = 0.33
        return form_score
    else:
        return 0.33

def get_h2h_score(home_team_id, away_team_id, years=3):
    # Obtenir les head-to-head
    h2h_params = {
        'h2h': f"{home_team_id}-{away_team_id}"
    }
    h2h_resp = requests.get(API_URL_FIXTURES, headers=headers, params=h2h_params)
    if h2h_resp.status_code == 200:
        h2h_data = h2h_resp.json().get('response', [])
        # On peut filtrer par date pour n'inclure que les 3 dernières saisons (si date dispo)
        # Pour simplifier, on prend tout.
        if len(h2h_data) == 0:
            return 0.33, 0.33  # Pas de données H2H, neutre

        total_matches = len(h2h_data)
        home_wins = 0
        away_wins = 0
        draws = 0
        for m in h2h_data:
            hg = m['goals']['home']
            ag = m['goals']['away']
            h_id = m['teams']['home']['id']
            a_id = m['teams']['away']['id']
            if hg == ag:
                draws += 1
            elif (h_id == home_team_id and hg > ag) or (a_id == home_team_id and ag > hg):
                home_wins += 1
            else:
                away_wins += 1
        # Scores normalisés
        home_h2h_score = home_wins / total_matches
        away_h2h_score = away_wins / total_matches
        return home_h2h_score, away_h2h_score
    else:
        return 0.33, 0.33

def get_odds_score(match_id):
    odds_params = {
        'fixture': match_id
    }
    odds_resp = requests.get(API_URL_ODDS, headers=headers, params=odds_params)
    if odds_resp.status_code == 200:
        odds_data = odds_resp.json().get('response', [])
        home_odds_list = []
        draw_odds_list = []
        away_odds_list = []
        for book in odds_data:
            for bookmaker in book.get('bookmakers', []):
                for bet in bookmaker.get('bets', []):
                    if bet['name'] == 'Match Winner':
                        for odd in bet['values']:
                            if odd['value'] == 'Home':
                                home_odds_list.append(float(odd['odd']))
                            elif odd['value'] == 'Draw':
                                draw_odds_list.append(float(odd['odd']))
                            elif odd['value'] == 'Away':
                                away_odds_list.append(float(odd['odd']))
        def avg_odd(lst):
            return sum(lst)/len(lst) if lst else None

        avg_home_odd = avg_odd(home_odds_list)
        avg_draw_odd = avg_odd(draw_odds_list)
        avg_away_odd = avg_odd(away_odds_list)

        # Conversion en probas
        def odd_to_prob(o):
            return 1/o if o and o > 0 else 0.33

        home_prob = odd_to_prob(avg_home_odd)
        draw_prob = odd_to_prob(avg_draw_odd)
        away_prob = odd_to_prob(avg_away_odd)
        return home_prob, draw_prob, away_prob
    else:
        return 0.33, 0.33, 0.33

def get_injury_factor(league_id, team_id):
    injuries_params = {
        'league': league_id,
        'season': datetime.datetime.now().year,
        'team': team_id
    }
    injuries_resp = requests.get('https://v3.football.api-sports.io/injuries', headers=headers, params=injuries_params)
    if injuries_resp.status_code == 200:
        injuries_data = injuries_resp.json().get('response', [])
        # On peut par exemple dire que plus il y a de blessés, plus on diminue le score.
        # Imaginons une échelle simple : 0 blessé = 1.0, 5 blessés = 0.5, etc.
        # injury_factor = max(0, 1 - (nombre_de_blesses * 0.1))
        count = len(injuries_data)
        injury_factor = max(0, 1 - count*0.05) # chaque blessé enlève 0.05
        return injury_factor
    else:
        return 0.9 # Valeur par défaut

def geocode_city(city_name):
    # Utilisation de Nominatim (OpenStreetMap) pour obtenir lat, lon
    # Attention : respecter les conditions d'utilisation d'OSM Nominatim (User-Agent)
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        'q': city_name,
        'format': 'json',
        'limit': 1
    }
    headers_geo = {'User-Agent': 'MyFootballApp/1.0'} 
    resp = requests.get(url, params=params, headers=headers_geo)
    if resp.status_code == 200:
        data = resp.json()
        if data:
            lat = float(data[0]['lat'])
            lon = float(data[0]['lon'])
            return lat, lon
    return None, None

def get_weather_factor(lat, lon, match_date):
    # Exemple pour Meteoblue. Il faut vérifier la doc pour obtenir la météo spécifique à une date.
    # Ici on simule (à adapter selon la doc Meteoblue)
    if lat is None or lon is None:
        return 0.8  # valeur par défaut

    weather_params = {
        'lat': lat,
        'lon': lon,
        'apikey': WEATHER_API_KEY,
        'format': 'json'
        # Ajouter d'autres paramètres selon la doc Meteoblue, 
        # éventuellement la date/heure du match, etc.
    }
    weather_resp = requests.get(API_URL_WEATHER, params=weather_params)
    if weather_resp.status_code == 200:
        weather_data = weather_resp.json()
        # Extraire les infos pertinentes (pluie, vent, etc.)
        # Supposons qu'on ait un champ 'rain' (mm) pour l'heure du match
        rain = weather_data.get('rain', 0)
        # On définit un weather_factor simple : plus il pleut, plus on diminue ce facteur
        weather_factor = max(0, 1 - rain*0.1)
        return weather_factor
    else:
        return 0.8  # par défaut

if match_id:
    # Récupérer le détail du match sélectionné
    selected_fixture = next((f for f in data_fixtures if f['fixture']['id'] == match_id), None)
    if selected_fixture:
        home_team_id = selected_fixture['teams']['home']['id']
        away_team_id = selected_fixture['teams']['away']['id']
        home_team_name = selected_fixture['teams']['home']['name']
        away_team_name = selected_fixture['teams']['away']['name']
        fixture_city = selected_fixture['fixture']['venue']['city']

        # Forme
        home_form_score = get_team_form(home_team_id, n=5) # entre 0 et 1
        away_form_score = get_team_form(away_team_id, n=5) # entre 0 et 1

        # H2H
        home_h2h_score, away_h2h_score = get_h2h_score(home_team_id, away_team_id) # entre 0 et 1

        # Odds
        home_odds_prob, draw_odds_prob, away_odds_prob = get_odds_score(match_id) # entre 0 et 1

        # Blessés
        home_injury_factor = get_injury_factor(league_id, home_team_id) # entre 0 et 1
        away_injury_factor = get_injury_factor(league_id, away_team_id) # entre 0 et 1

        # Géolocalisation
        lat, lon = geocode_city(fixture_city)

        # Météo
        weather_factor = get_weather_factor(lat, lon, selected_date) # entre 0 et 1

        # Pondérations (exemple)
        weight_form = 0.3
        weight_h2h = 0.2
        weight_odds = 0.3
        weight_weather = 0.1
        weight_injury = 0.1

        # Calcul des "scores" (non normalisés, mais tous entre 0 et 1)
        home_base = (home_form_score * weight_form +
                     home_h2h_score * weight_h2h +
                     home_odds_prob * weight_odds +
                     weather_factor * weight_weather +
                     home_injury_factor * weight_injury)

        away_base = (away_form_score * weight_form +
                     away_h2h_score * weight_h2h +
                     away_odds_prob * weight_odds +
                     weather_factor * weight_weather +
                     away_injury_factor * weight_injury)

        # Pour le nul, on peut se baser principalement sur la cote du nul et la météo par exemple
        draw_base = (draw_odds_prob * 0.7 + weather_factor * 0.3)

        # S'assurer qu'aucune valeur n'est négative (normalement impossible avec les ratios)
        home_base = max(home_base, 0)
        away_base = max(away_base, 0)
        draw_base = max(draw_base, 0)

        # Normalisation
        total = home_base + away_base + draw_base
        if total > 0:
            home_prob = home_base / total
            draw_prob = draw_base / total
            away_prob = away_base / total
        else:
            home_prob = draw_prob = away_prob = 1/3.0

        st.write("### Probabilités estimées :")
        st.write(f"- {home_team_name} gagne : {home_prob*100:.2f}%")
        st.write(f"- Match nul : {draw_prob*100:.2f}%")
        st.write(f"- {away_team_name} gagne : {away_prob*100:.2f}%")

        st.write("Note : Ces probabilités sont purement indicatives. Affinez les pondérations et la logique selon vos besoins.")
    else:
        st.info("Aucun détail de match disponible.")

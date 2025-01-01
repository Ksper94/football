import streamlit as st
import requests
from datetime import date
import datetime

# ===================== CONFIGURATION DE LA PAGE ==========================
st.set_page_config(page_title="Prédictions de Matchs", page_icon="⚽")

# ===================== CONFIGURATIONS D'AUTHENTIFICATION =================
NEXTJS_LOGIN_URL = "https://foot-predictions.com/api/login"  # À adapter selon votre domaine

# Initialisation de l'état de la session pour l'authentification
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

# Fonction pour gérer l'authentification via e-mail + mot de passe
def handle_login(email, password):
    try:
        # Envoi des identifiants au backend
        resp = requests.post(NEXTJS_LOGIN_URL, json={"email": email, "password": password})
        if resp.status_code == 200:
            data = resp.json()
            if data.get('success', False):
                # Authentification réussie
                st.session_state.authenticated = True
                st.success(data.get('message', "Authentification réussie !"))
                st.rerun()  # Recharge l'application pour afficher le contenu protégé
            else:
                # Échec de l'authentification (mauvais identifiants ou abonnement expiré)
                st.error(data.get('message', "Impossible de s'authentifier."))
        else:
            # Erreur côté backend
            st.error(f"Erreur API (code HTTP: {resp.status_code}).")
    except Exception as e:
        st.error(f"Erreur lors de la tentative de login: {e}")

# Affichage du formulaire de connexion si non authentifié
if not st.session_state.authenticated:
    st.title("Connexion à l'application")

    email = st.text_input("Email")
    password = st.text_input("Mot de passe", type="password")

    if st.button("Se connecter"):
        if email and password:
            handle_login(email, password)
        else:
            st.error("Veuillez renseigner votre email et votre mot de passe.")
    st.stop()

# ===================== CONTENU DE L'APPLICATION ==========================
st.title("Bienvenue dans l'application de Prédiction de Matchs")
st.write("Vous êtes authentifié avec succès (abonnement valide).")
st.markdown("""
*Bienvenue dans notre outil de prédiction de matchs de football. Sélectionnez une date, un continent, un pays, puis une compétition.
Notre algorithme calcule les probabilités en tenant compte de nombreux facteurs : forme des équipes, historique des confrontations, cotes, météo, blessures, etc.*  
""")

# ===================== API CONFIGURATION ==========================
API_KEY = 'aa14874600855457b5a838ec894a06ae'
WEATHER_API_KEY = 'mOpwoft03br5cj7z'

# URLs de base pour l'API Football
API_URL_LEAGUES = 'https://v3.football.api-sports.io/leagues'
API_URL_FIXTURES = 'https://v3.football.api-sports.io/fixtures'
API_URL_TEAMS = 'https://v3.football.api-sports.io/teams'
API_URL_STANDINGS = 'https://v3.football.api-sports.io/standings'
API_URL_ODDS = 'https://v3.football.api-sports.io/odds'
API_URL_WEATHER = 'https://my.meteoblue.com/packages/basic-1h'

headers = {
    'x-apisports-key': API_KEY,
    'x-apisports-host': 'v3.football.api-sports.io'
}

# Sélection de la date
today = date.today()
selected_date = st.date_input("Sélectionnez une date (à partir d'aujourd'hui):", min_value=today, value=today)

# Détermination de la saison basée sur la date sélectionnée
# Supposons que la saison commence en août et finit en mai de l'année suivante
if selected_date.month < 8:  # Si avant août, c'est la saison précédente
    season_year = selected_date.year - 1
else:
    season_year = selected_date.year

# Continents
continents = ["Europe", "South America", "North America", "Asia", "Africa"]
selected_continent = st.selectbox("Sélectionnez un continent :", continents)

# Liste de grandes compétitions européennes (IDs à adapter)
european_top_competitions = {
    "UEFA Champions League": 2,
    "UEFA Europa League": 3,
    "UEFA Europa Conference League": 848
}

response = requests.get(API_URL_LEAGUES, headers=headers)
if response.status_code == 200:
    data_leagues = response.json().get('response', [])
    all_countries = list(set([league['country']['name'] 
                              for league in data_leagues 
                              if 'country' in league and league['country']['name']]))
    all_countries.sort()

    if selected_continent == "Europe":
        all_countries = ["International"] + all_countries
    selected_country = st.selectbox("Sélectionnez un pays :", all_countries)
else:
    st.error("Impossible de récupérer la liste des ligues.")
    selected_country = None
    data_leagues = []

if selected_country:
    if selected_continent == "Europe" and selected_country == "International":
        comp_options = list(european_top_competitions.keys())
        selected_league_name = st.selectbox("Sélectionnez une grande compétition européenne :", comp_options)
        league_id = european_top_competitions[selected_league_name]
        league_info = next((l for l in data_leagues if l['league']['id'] == league_id), None)
    else:
        leagues_in_country = [league for league in data_leagues if league['country']['name'] == selected_country]
        league_names = [l['league']['name'] for l in leagues_in_country]
        league_names.sort()
        selected_league_name = st.selectbox("Sélectionnez une compétition :", league_names)
        selected_league = next((l for l in leagues_in_country if l['league']['name'] == selected_league_name), None)
        league_id = selected_league['league']['id'] if selected_league else None
        league_info = selected_league
else:
    league_id = None
    league_info = None

if league_id:
    params_fixtures = {
        'league': league_id,
        'season': season_year,  # Utilisation de la saison calculée
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
            selected_match_str = st.selectbox("Sélectionnez un match :", [m[0] for m in match_list])
            match_id = next((m[1] for m in match_list if m[0] == selected_match_str), None)
        else:
            st.info("Aucun match trouvé pour la date et la compétition sélectionnées.")
            match_id = None
    else:
        st.error("Impossible de récupérer les matchs.")
        match_id = None
else:
    match_id = None

# ... (le reste de votre code concernant l'affichage des détails du match, calcul des probabilités, etc. reste inchangé)
def get_team_form(team_id, n=5):
    form_params = {
        'team': team_id,
        'last': n
    }
    form_resp = requests.get(API_URL_FIXTURES, headers=headers, params=form_params)
    if form_resp.status_code == 200:
        form_data = form_resp.json().get('response', [])
        wins, draws, losses = 0, 0, 0
        for m in form_data:
            hg = m['goals'].get('home') if m['goals'].get('home') is not None else 0
            ag = m['goals'].get('away') if m['goals'].get('away') is not None else 0
            h_id = m['teams']['home']['id']
            a_id = m['teams']['away']['id']
            
            if h_id == team_id:
                if hg > ag:
                    wins += 1
                elif hg == ag:
                    draws += 1
                else:
                    losses += 1
            else:
                if ag > hg:
                    wins += 1
                elif ag == hg:
                    draws += 1
                else:
                    losses += 1

        total = wins + draws + losses
        form_score = wins / total if total > 0 else 0.33
        return form_score
    else:
        return 0.33

def get_h2h_score(home_team_id, away_team_id):
    h2h_params = {
        'h2h': f"{home_team_id}-{away_team_id}"
    }
    h2h_resp = requests.get(API_URL_FIXTURES, headers=headers, params=h2h_params)
    if h2h_resp.status_code == 200:
        h2h_data = h2h_resp.json().get('response', [])
        if len(h2h_data) == 0:
            return 0.33, 0.33
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

        def odd_to_prob(o):
            return 1/o if (o and o > 0) else 0.33

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
        count = len(injuries_data)
        # Hypothèse : chaque blessure réduit un peu la "forme" de l'équipe
        injury_factor = max(0, 1 - count * 0.05)
        return injury_factor
    else:
        return 0.9

def geocode_city(city_name):
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
    if lat is None or lon is None:
        return 0.8
    weather_params = {
        'lat': lat,
        'lon': lon,
        'apikey': WEATHER_API_KEY,
        'format': 'json'
    }
    weather_resp = requests.get(API_URL_WEATHER, params=weather_params)
    if weather_resp.status_code == 200:
        weather_data = weather_resp.json()
        # Hypothèse : s'il y a de la pluie, on pénalise un peu la qualité du match
        rain = weather_data.get('rain', 0)
        weather_factor = max(0, 1 - rain*0.1)
        return weather_factor
    else:
        return 0.8

# ===================== LOGIQUE DE MATCH / CALCULS =====================
if 'match_id' not in st.session_state:
    st.session_state.match_id = None

if league_id:
    if response_fixtures.status_code == 200:
        # On a déjà récupéré la liste data_fixtures
        pass
    else:
        st.error("Impossible de récupérer les matchs.")

if match_id:
    st.session_state.match_id = match_id

if st.session_state.match_id:
    selected_fixture = next((f for f in data_fixtures 
                             if f['fixture']['id'] == st.session_state.match_id), None)
    if selected_fixture:
        home_team_id = selected_fixture['teams']['home']['id']
        away_team_id = selected_fixture['teams']['away']['id']
        home_team_name = selected_fixture['teams']['home']['name']
        away_team_name = selected_fixture['teams']['away']['name']
        home_team_logo = selected_fixture['teams']['home']['logo']
        away_team_logo = selected_fixture['teams']['away']['logo']
        fixture_city = selected_fixture['fixture']['venue']['city']

        # Affichage du logo de la compétition si dispo
        if league_info and 'league' in league_info and 'logo' in league_info['league']:
            st.image(league_info['league']['logo'], width=80)
        
        st.markdown(f"### {selected_league_name}")
        st.write(f"**Date du match :** {selected_date.strftime('%d %B %Y')}")

        col1, col2, col3 = st.columns([1,1,1])
        with col1:
            st.image(home_team_logo, width=80)
            st.write(f"**{home_team_name}**")

        with col2:
            st.markdown("<h2 style='text-align: center;'>VS</h2>", unsafe_allow_html=True)

        with col3:
            st.image(away_team_logo, width=80)
            st.write(f"**{away_team_name}**")

        st.markdown("---")

        # Calcul des différents scores
        home_form_score = get_team_form(home_team_id, n=5)
        away_form_score = get_team_form(away_team_id, n=5)

        home_h2h_score, away_h2h_score = get_h2h_score(home_team_id, away_team_id)
        home_odds_prob, draw_odds_prob, away_odds_prob = get_odds_score(st.session_state.match_id)
        home_injury_factor = get_injury_factor(league_id, home_team_id)
        away_injury_factor = get_injury_factor(league_id, away_team_id)

        lat, lon = geocode_city(fixture_city)
        weather_factor = get_weather_factor(lat, lon, selected_date)

        # Pondérations
        weight_form = 0.3
        weight_h2h = 0.2
        weight_odds = 0.3
        weight_weather = 0.1
        weight_injury = 0.1

        home_base = (
            home_form_score * weight_form +
            home_h2h_score * weight_h2h +
            home_odds_prob  * weight_odds +
            weather_factor  * weight_weather +
            home_injury_factor * weight_injury
        )

        away_base = (
            away_form_score * weight_form +
            away_h2h_score * weight_h2h +
            away_odds_prob  * weight_odds +
            weather_factor  * weight_weather +
            away_injury_factor * weight_injury
        )

        draw_base = draw_odds_prob * 0.7 + weather_factor * 0.3

        total = home_base + away_base + draw_base
        if total > 0:
            home_prob = home_base / total
            draw_prob = draw_base / total
            away_prob = away_base / total
        else:
            home_prob = draw_prob = away_prob = 1/3.0

        st.subheader("Probabilités estimées du résultat")
        st.write(f"- **{home_team_name} gagne :** {home_prob*100:.2f}%")
        st.write(f"- **Match nul :** {draw_prob*100:.2f}%")
        st.write(f"- **{away_team_name} gagne :** {away_prob*100:.2f}%")

        st.markdown("---")
        st.markdown("""
        **Important :** Les probabilités affichées ci-dessus sont générées grâce à un modèle complexe prenant 
        en compte de multiples facteurs. Bien que notre algorithme soit conçu pour fournir les estimations 
        les plus fiables possibles, le résultat d'un match reste influencé par de nombreux éléments imprévisibles.

        Notre outil vous offre un avantage analytique, mais ne constitue pas une garantie de résultats. 
        Utilisez ces informations avec discernement.
        """)
    else:
        st.info("Aucun détail de match disponible.")
else:
    pass  # Aucune fixture sélectionnée

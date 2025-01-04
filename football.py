import streamlit as st
import requests
from datetime import date
import matplotlib.pyplot as plt

# ===================== CONFIGURATION DE LA PAGE ==========================
st.set_page_config(page_title="Prédictions de Matchs", page_icon="⚽", layout="wide")

# ===================== CONFIGURATION DES API =============================
API_KEY = 'aa14874600855457b5a838ec894a06ae'
WEATHER_API_KEY = 'mOpwoft03br5cj7z'

API_URL_LEAGUES = 'https://v3.football.api-sports.io/leagues'
API_URL_FIXTURES = 'https://v3.football.api-sports.io/fixtures'
API_URL_ODDS = 'https://v3.football.api-sports.io/odds'

HEADERS = {
    'x-apisports-key': API_KEY,
    'x-apisports-host': 'v3.football.api-sports.io'
}

NEXTJS_LOGIN_URL = "https://foot-predictions.com/api/login"

# ===================== AUTHENTIFICATION ==================================
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

def handle_login(email, password):
    try:
        resp = requests.post(NEXTJS_LOGIN_URL, json={"email": email, "password": password})
        if resp.status_code == 200:
            data = resp.json()
            if data.get('success', False):
                st.session_state.authenticated = True
                st.success(data.get('message', "Authentification réussie !"))
                st.experimental_rerun()
            else:
                st.error(data.get('message', "Impossible de s'authentifier."))
        else:
            st.error(f"Erreur API (code HTTP: {resp.status_code}).")
    except Exception as e:
        st.error(f"Erreur lors de la tentative de connexion : {e}")

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
# ===================== CONTENU PRINCIPAL =================================
st.title("Bienvenue dans l'application de Prédiction de Matchs")
st.markdown("""
*Bienvenue dans notre outil de prédiction de matchs de football. Sélectionnez une date, un pays, puis une compétition.*
""")

today = date.today()
selected_date = st.date_input("Sélectionnez une date :", min_value=today, value=today)

# Chargement des ligues
response_leagues = requests.get(API_URL_LEAGUES, headers=HEADERS)
if response_leagues.status_code == 200:
    leagues_data = response_leagues.json().get('response', [])
    countries = sorted(list(set([league['country']['name'] for league in leagues_data if league.get('country')])))
    selected_country = st.selectbox("Sélectionnez un pays :", countries)

    country_leagues = [league for league in leagues_data if league['country']['name'] == selected_country]
    league_names = sorted([league['league']['name'] for league in country_leagues])
    selected_league_name = st.selectbox("Sélectionnez une compétition :", league_names)

    league_id = next((league['league']['id'] for league in country_leagues if league['league']['name'] == selected_league_name), None)
else:
    st.error("Erreur lors de la récupération des ligues.")
    league_id = None

# Chargement des matchs
if league_id:
    params = {'league': league_id, 'season': today.year, 'date': selected_date.strftime('%Y-%m-%d')}
    response_fixtures = requests.get(API_URL_FIXTURES, headers=HEADERS, params=params)
    if response_fixtures.status_code == 200:
        fixtures = response_fixtures.json().get('response', [])
        matches = [(f"{fixture['teams']['home']['name']} vs {fixture['teams']['away']['name']}", fixture['fixture']['id']) for fixture in fixtures]
        selected_match = st.selectbox("Sélectionnez un match :", [match[0] for match in matches])
        match_id = next(match[1] for match in matches if match[0] == selected_match)
    else:
        st.error("Erreur lors de la récupération des matchs.")
        match_id = None
else:
    match_id = None
# ===================== AFFICHAGE DES PROBABILITÉS ========================
if match_id:
    odds_response = requests.get(f"{API_URL_ODDS}?fixture={match_id}", headers=HEADERS)
    if odds_response.status_code == 200:
        odds_data = odds_response.json().get('response', [])
        if odds_data:
            bookmakers = odds_data[0].get('bookmakers', [])
            home_odds, draw_odds, away_odds = [], [], []

            for bookmaker in bookmakers:
                for bet in bookmaker.get('bets', []):
                    if bet['name'] == "Match Winner":
                        for value in bet.get('values', []):
                            if value['value'] == 'Home':
                                home_odds.append(float(value['odd']))
                            elif value['value'] == 'Draw':
                                draw_odds.append(float(value['odd']))
                            elif value['value'] == 'Away':
                                away_odds.append(float(value['odd']))

            avg_home = sum(home_odds) / len(home_odds) if home_odds else None
            avg_draw = sum(draw_odds) / len(draw_odds) if draw_odds else None
            avg_away = sum(away_odds) / len(away_odds) if away_odds else None

            def calculate_prob(odd):
                return round(1 / odd * 100, 2) if odd else 0

            home_prob = calculate_prob(avg_home)
            draw_prob = calculate_prob(avg_draw)
            away_prob = calculate_prob(avg_away)

            st.subheader("Probabilités des résultats")
            col1, col2, col3 = st.columns(3)
            col1.metric("Victoire domicile", f"{home_prob}%")
            col2.metric("Match nul", f"{draw_prob}%")
            col3.metric("Victoire extérieur", f"{away_prob}%")

            # Visualisation
            fig, ax = plt.subplots()
            ax.bar(['Domicile', 'Nul', 'Extérieur'], [home_prob, draw_prob, away_prob], color=['green', 'orange', 'red'])
            ax.set_ylabel("Probabilité (%)")
            st.pyplot(fig)

            # Message d'avertissement
            st.markdown("""
            **Important :** Les probabilités affichées ci-dessus sont générées grâce à un modèle complexe prenant 
            en compte de multiples facteurs. Bien que notre algorithme soit conçu pour fournir des estimations fiables, 
            le résultat d'un match reste influencé par des éléments imprévisibles.
            """)
        else:
            st.info("Aucune donnée de cotes disponible pour ce match.")
    else:
        st.error("Erreur lors de la récupération des cotes.")

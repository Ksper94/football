import streamlit as st
import requests
from openai import OpenAI  # <-- Nouvel import
from datetime import date
import datetime

# ===================== CONFIGURATION DE LA PAGE ==========================
st.set_page_config(
    page_title="Prédictions de Matchs",
    page_icon="⚽",
    layout="centered"
)

# ===================== CLÉS SECRÈTES ====================================
# Récupération des clés depuis Streamlit Cloud (ou .streamlit/secrets.toml)
API_KEY = st.secrets["API_KEY"]
WEATHER_API_KEY = st.secrets["WEATHER_API_KEY"]
OPENAI_KEY = st.secrets["OPENAI_API_KEY"]

# Instanciation du client typed OpenAI
client = OpenAI(api_key=OPENAI_KEY)

# ===================== FONCTION GÉNÉRATION TEXTE IA (NOUVELLE API) ======
def generate_ai_analysis(
    home_team_name, away_team_name,
    home_prob, draw_prob, away_prob,
    home_form_score, away_form_score,
    home_h2h_score, away_h2h_score
):
    """
    Génère un court texte de synthèse via la nouvelle interface 
    client.chat.completions.create().
    """
    prompt = f"""
Écris un court commentaire en français sur le match suivant :
- Équipe à domicile : {home_team_name} (probabilité de gagner : {home_prob*100:.1f}%)
- Équipe à l'extérieur : {away_team_name} (probabilité de gagner : {away_prob*100:.1f}%)
- Probabilité de match nul : {draw_prob*100:.1f}%
- Forme récente de {home_team_name} : {home_form_score:.2f} (sur 1 max)
- Forme récente de {away_team_name} : {away_form_score:.2f} (sur 1 max)
- Historique des confrontations directes (H2H) : 
    * {home_team_name} : {home_h2h_score:.2f}
    * {away_team_name} : {away_h2h_score:.2f}

Donne un petit paragraphe expliquant brièvement la situation et ce à quoi on peut s'attendre.
Ne dépasse pas 80 mots environ.
N'invente pas de statistiques supplémentaires.
    """

    try:
        completion = client.chat.completions.create(
            model="gpt-3.5-turbo",  # ou "gpt-4", "gpt-4o", etc. selon ton accès
            messages=[
                {"role": "user", "content": prompt}
            ],
            max_tokens=150,
            temperature=0.7,
            top_p=1,
            frequency_penalty=0,
            presence_penalty=0
        )
        # On récupère le texte
        analysis_text = completion.choices[0].message.content.strip()
        return analysis_text

    except Exception as e:
        st.error(f"Erreur lors de la génération du texte IA : {e}")
        return None

# ===================== AUTHENTIFICATION ==========================
NEXTJS_LOGIN_URL = "https://foot-predictions.com/api/login"

if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

def handle_login(email, password):
    """Exemple d’appel à ton backend NextJS pour login."""
    try:
        resp = requests.post(NEXTJS_LOGIN_URL, json={"email": email, "password": password})
        if resp.status_code == 200:
            data = resp.json()
            if data.get('success', False):
                st.session_state.authenticated = True
                st.success(data.get('message', "Authentification réussie !"))
                st.rerun()
            else:
                st.error(data.get('message', "Impossible de s'authentifier."))
        else:
            st.error(f"Erreur API (code HTTP: {resp.status_code}).")
    except Exception as e:
        st.error(f"Erreur lors de la tentative de login: {e}")

# ===================== FORMULAIRE DE CONNEXION ===================
if not st.session_state.authenticated:
    st.markdown("<h2 class='title'>⚽ Connexion à l'application</h2>", unsafe_allow_html=True)
    st.markdown("<p class='subtitle'>Veuillez renseigner vos identifiants pour accéder aux prédictions.</p>", unsafe_allow_html=True)

    email = st.text_input("Email")
    password = st.text_input("Mot de passe", type="password")

    if st.button("Se connecter"):
        if email and password:
            handle_login(email, password)
        else:
            st.error("Veuillez renseigner votre email et votre mot de passe.")
    st.stop()

# ===================== PAGE PRINCIPALE ============================
st.markdown("<h2 class='title'>Bienvenue dans l'application de Prédiction de Matchs</h2>", unsafe_allow_html=True)
st.markdown("<p class='subtitle'>Vous êtes authentifié avec succès (abonnement valide).</p>", unsafe_allow_html=True)

st.write(
    "Bienvenue dans notre outil de prédiction de matchs de football. "
    "Sélectionnez une date, un continent, un pays, puis une compétition.\n\n"
    "Notre algorithme calcule les probabilités en tenant compte de nombreux facteurs : "
    "_forme des équipes, historique des confrontations, cotes, météo, blessures, etc._"
)
st.markdown("<hr class='hr-separator'/>", unsafe_allow_html=True)

# ===================== API FOOTBALL ==============================
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

# ===================== SÉLECTION DE LA DATE ======================
today = date.today()
selected_date = st.date_input(
    "Sélectionnez une date (à partir d'aujourd'hui) :",
    min_value=today,
    value=today
)

# Calcul de la saison
season_year = selected_date.year - 1 if selected_date.month < 8 else selected_date.year

# Sélection du continent
continents = ["Europe", "South America", "North America", "Asia", "Africa"]
selected_continent = st.selectbox("Sélectionnez un continent :", continents)

# Leagues pour l'Europe
european_top_competitions = {
    "UEFA Champions League": 2,
    "UEFA Europa League": 3,
    "UEFA Europa Conference League": 848
}

response = requests.get(API_URL_LEAGUES, headers=headers)
if response.status_code == 200:
    data_leagues = response.json().get('response', [])
    all_countries = list({
        league['country']['name']
        for league in data_leagues 
        if league.get('country', {}).get('name')
    })
    all_countries.sort()

    if selected_continent == "Europe":
        # On ajoute "International" pour les compétitions type Champions League
        all_countries = ["International"] + all_countries

    selected_country = st.selectbox("Sélectionnez un pays :", all_countries)
else:
    st.error("Impossible de récupérer la liste des ligues.")
    selected_country = None
    data_leagues = []

# ===================== CHOIX DE LA COMPÉTITION ==================
if selected_country:
    if selected_continent == "Europe" and selected_country == "International":
        comp_options = list(european_top_competitions.keys())
        selected_league_name = st.selectbox("Sélectionnez une grande compétition européenne :", comp_options)
        league_id = european_top_competitions[selected_league_name]
        league_info = next((l for l in data_leagues if l['league']['id'] == league_id), None)
    else:
        leagues_in_country = [l for l in data_leagues if l['country']['name'] == selected_country]
        league_names = sorted([l['league']['name'] for l in leagues_in_country])
        selected_league_name = st.selectbox("Sélectionnez une compétition :", league_names)
        selected_league = next((l for l in leagues_in_country if l['league']['name'] == selected_league_name), None)
        league_id = selected_league['league']['id'] if selected_league else None
        league_info = selected_league
else:
    league_id = None
    league_info = None

# ===================== LISTE DES MATCHS =========================
if league_id:
    params_fixtures = {
        'league': league_id,
        'season': season_year,
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
            selected_match_str = st.selectbox(
                "Sélectionnez un match :",
                [m[0] for m in match_list]
            )
            match_id = next((m[1] for m in match_list if m[0] == selected_match_str), None)
        else:
            st.info("Aucun match trouvé pour la date et la compétition sélectionnées.")
            match_id = None
    else:
        st.error("Impossible de récupérer les matchs.")
        match_id = None
else:
    match_id = None

# ===================== FONCTIONS COMPLÉMENTAIRES =================
def get_team_form(team_id, n=5):
    """Retourne la forme d’une équipe sur les n derniers matchs (0 à 1)."""
    form_params = {'team': team_id, 'last': n}
    resp = requests.get(API_URL_FIXTURES, headers=headers, params=form_params)
    if resp.status_code == 200:
        form_data = resp.json().get('response', [])
        wins, draws, losses = 0, 0, 0
        for m in form_data:
            hg = m['goals'].get('home') or 0
            ag = m['goals'].get('away') or 0
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
        return wins / total if total > 0 else 0.33
    return 0.33

def get_h2h_score(home_team_id, away_team_id):
    """Retourne la proportion de victoires domicile et extérieures sur l’historique H2H."""
    h2h_params = {'h2h': f"{home_team_id}-{away_team_id}"}
    resp = requests.get(API_URL_FIXTURES, headers=headers, params=h2h_params)
    if resp.status_code == 200:
        h2h_data = resp.json().get('response', [])
        if not h2h_data:
            # Pas de match H2H : on renvoie un score neutre
            return 0.33, 0.33
        total_matches = len(h2h_data)
        home_wins, away_wins, draws = 0, 0, 0
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
    return 0.33, 0.33

def get_odds_score(match_id):
    """Retourne la probabilité implicite (home, draw, away) selon les cotes des bookmakers."""
    odds_params = {'fixture': match_id}
    resp = requests.get(API_URL_ODDS, headers=headers, params=odds_params)
    if resp.status_code == 200:
        odds_data = resp.json().get('response', [])
        if not odds_data:
            return 0.33, 0.33, 0.33

        home_odds, draw_odds, away_odds = [], [], []
        for book in odds_data:
            for bookmaker in book.get('bookmakers', []):
                for bet in bookmaker.get('bets', []):
                    if bet['name'] == 'Match Winner':
                        for odd in bet.get('values', []):
                            if 'value' in odd and 'odd' in odd:
                                if odd['value'] == 'Home':
                                    home_odds.append(float(odd['odd']))
                                elif odd['value'] == 'Draw':
                                    draw_odds.append(float(odd['odd']))
                                elif odd['value'] == 'Away':
                                    away_odds.append(float(odd['odd']))

        def avg_odd(lst):
            return sum(lst) / len(lst) if lst else None

        avg_home = avg_odd(home_odds) or 3.0
        avg_draw = avg_odd(draw_odds) or 3.0
        avg_away = avg_odd(away_odds) or 3.0

        def odd_to_prob(o):
            return 1 / o if (o and o > 0) else 0.33

        return odd_to_prob(avg_home), odd_to_prob(avg_draw), odd_to_prob(avg_away)
    return 0.33, 0.33, 0.33

def get_injury_factor(league_id, team_id):
    """Réduit la forme de l’équipe en fonction du nombre de blessés."""
    injuries_params = {
        'league': league_id,
        'season': datetime.datetime.now().year,
        'team': team_id
    }
    resp = requests.get('https://v3.football.api-sports.io/injuries', headers=headers, params=injuries_params)
    if resp.status_code == 200:
        injuries_data = resp.json().get('response', [])
        count = len(injuries_data)
        return max(0, 1 - count * 0.05)
    return 0.9

def geocode_city(city_name):
    """Retourne la latitude/longitude d’une ville."""
    url = "https://nominatim.openstreetmap.org/search"
    params = {'q': city_name, 'format': 'json', 'limit': 1}
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
    """Renvoie un facteur météo (ex: 0.8 si pluie, 1.0 si temps clair)."""
    if lat is None or lon is None:
        return 0.8
    weather_params = {
        'lat': lat,
        'lon': lon,
        'apikey': WEATHER_API_KEY,
        'format': 'json'
    }
    resp = requests.get(API_URL_WEATHER, params=weather_params)
    if resp.status_code == 200:
        weather_data = resp.json()
        # Simplification : si 'rain' existe, on applique un malus
        rain = weather_data.get('rain', 0)
        return max(0, 1 - rain * 0.1)
    return 0.8

# ===================== AFFICHAGE FINAL ===========================
if 'match_id' not in st.session_state:
    st.session_state.match_id = None

if league_id and match_id:
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

        # Logo de la compétition (si dispo)
        if league_info and 'league' in league_info and 'logo' in league_info['league']:
            st.image(league_info['league']['logo'], width=80)

        st.write(f"### {selected_league_name}")
        st.write(f"**Date du match :** {selected_date.strftime('%d %B %Y')}")

        col1, col2, col3 = st.columns([1, 1, 1])
        with col1:
            st.image(home_team_logo, width=80)
            st.write(f"**{home_team_name}**")

        with col2:
            st.markdown("<h3 style='text-align:center;'>VS</h3>", unsafe_allow_html=True)

        with col3:
            st.image(away_team_logo, width=80)
            st.write(f"**{away_team_name}**")

        st.markdown("<hr class='hr-separator'/>", unsafe_allow_html=True)

        # Calculs divers
        home_form_score = get_team_form(home_team_id, n=5)
        away_form_score = get_team_form(away_team_id, n=5)

        home_h2h_score, away_h2h_score = get_h2h_score(home_team_id, away_team_id)
        home_odds_prob, draw_odds_prob, away_odds_prob = get_odds_score(st.session_state.match_id)
        home_injury_factor = get_injury_factor(league_id, home_team_id)
        away_injury_factor = get_injury_factor(league_id, away_team_id)

        lat, lon = geocode_city(fixture_city)
        weather_factor = get_weather_factor(lat, lon, selected_date)

        # Pondérations ajustables
        weight_form = 0.3
        weight_h2h = 0.2
        weight_odds = 0.3
        weight_weather = 0.1
        weight_injury = 0.1

        home_base = (
            home_form_score * weight_form +
            home_h2h_score * weight_h2h +
            home_odds_prob * weight_odds +
            weather_factor * weight_weather +
            home_injury_factor * weight_injury
        )

        away_base = (
            away_form_score * weight_form +
            away_h2h_score * weight_h2h +
            away_odds_prob * weight_odds +
            weather_factor * weight_weather +
            away_injury_factor * weight_injury
        )

        draw_base = draw_odds_prob * 0.7 + weather_factor * 0.3
        total = home_base + away_base + draw_base
        if total > 0:
            home_prob = home_base / total
            draw_prob = draw_base / total
            away_prob = away_base / total
        else:
            home_prob = draw_prob = away_prob = 1/3

        st.subheader("Probabilités estimées du résultat :")
        st.write(f"- **{home_team_name} gagne :** {home_prob*100:.2f}%")
        st.write(f"- **Match nul :** {draw_prob*100:.2f}%")
        st.write(f"- **{away_team_name} gagne :** {away_prob*100:.2f}%")



        # =================== APPEL IA POUR TEXTE DE SYNTHÈSE ===================
        st.markdown("<hr class='hr-separator'/>", unsafe_allow_html=True)
        st.subheader("Analyse IA :")

        analysis_text = generate_ai_analysis(
            home_team_name, away_team_name,
            home_prob, draw_prob, away_prob,
            home_form_score, away_form_score,
            home_h2h_score, away_h2h_score
        )

        if analysis_text:
            st.write(analysis_text)

        st.markdown("<hr class='hr-separator'/>", unsafe_allow_html=True)
        st.write(
            "**Important :** Les probabilités affichées ci-dessus sont générées "
            "grâce à un modèle complexe tenant compte de multiples facteurs. "
            "Bien que notre algorithme soit conçu pour fournir des estimations "
            "fiables, le résultat d'un match reste soumis à de nombreux aléas.\n\n"
            "Notre outil vous donne un avantage analytique, **mais ne constitue pas une garantie**. "
            "Utilisez ces informations avec discernement."
        )
    else:
        st.info("Aucun détail de match disponible.")

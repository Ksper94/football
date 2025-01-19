# app.py
from datetime import datetime, date, timedelta
import pytz
import streamlit as st
from supabase_config import supabase
from openai import OpenAI  # Assurez-vous que OpenAI est installé : pip install openai
import requests

# ===================== CONFIGURATION DE LA PAGE ==========================
st.set_page_config(
    page_title="Prédictions de Matchs",
    page_icon="⚽",
    layout="centered"
)

# ===================== CLÉS SECRÈTES =====================================
API_KEY = st.secrets["API_KEY"]
WEATHER_API_KEY = st.secrets["WEATHER_API_KEY"]
OPENAI_KEY = st.secrets["OPENAI_API_KEY"]
POSITIONSTACK_API_KEY = st.secrets["POSITIONSTACK_API_KEY"]

# ===================== INITIALISATION DE L'IA ===========================
client = OpenAI(api_key=OPENAI_KEY)

# ===================== MAPPING PAYS “PHARES” PAR CONTINENT ====================
def reorder_countries(continent, all_countries):
    """
    Réordonne les pays pour mettre en premier ceux considérés comme “phares”
    dans le foot (par continent), puis le reste en ordre alphabétique.
    """
    top_countries_by_continent = {
        "Europe": [
            "France", "England", "Spain", "Italy", "Germany", 
            "Portugal", "Netherlands", "Belgium", "Turkey"
        ],
        "South America": ["Brazil", "Argentina", "Colombia", "Uruguay", "Chile"],
        "North America": ["United States", "Mexico", "Canada"],
        "Asia": ["Japan", "South Korea", "Saudi Arabia"],
        "Africa": ["Egypt", "Senegal", "Morocco", "Tunisia", "Algeria"]
    }
    
    top_countries = top_countries_by_continent.get(continent, [])
    top_list = [c for c in top_countries if c in all_countries]  # pays phares présents
    remaining = [c for c in all_countries if c not in top_list]
    remaining.sort()
    return top_list + remaining

# ===================== MAPPING D1 (COMPÉTITIONS PHARES) PAR PAYS ============
top_leagues_names = {
    "France": ["Ligue 1"],
    "England": ["Premier League"],
    "Spain": ["La Liga", "Primera Division"],
    "Italy": ["Serie A"],
    "Germany": ["Bundesliga"],
    "Portugal": ["Primeira Liga"],
    "Netherlands": ["Eredivisie"],
    "Belgium": ["Jupiler Pro League"],
    "Turkey": ["Süper Lig"],

    "Brazil": ["Serie A"],
    "Argentina": ["Liga Profesional Argentina", "Primera Division"],
    "Mexico": ["Liga MX"],
    "United States": ["MLS"],
    # etc.
}

# ===================== FONCTION GÉNÉRATION TEXTE IA =======================
def generate_ai_analysis(
    home_team_name, away_team_name,
    home_prob, draw_prob, away_prob,
    home_form_score, away_form_score,
    home_h2h_score, away_h2h_score
):
    """
    Génère un court texte de synthèse via l’API OpenAI (ChatGPT).
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
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150,
            temperature=0.7,
            top_p=1,
            frequency_penalty=0,
            presence_penalty=0
        )
        analysis_text = completion.choices[0].message.content.strip()
        return analysis_text

    except Exception as e:
        st.error(f"Erreur lors de la génération du texte IA : {e}")
        return None

# ===================== FONCTIONS D'AUTHENTIFICATION ET VÉRIFICATION ===========================
def authenticate_user(email, password):
    """
    Authentifie l'utilisateur via Supabase.
    Retourne l'objet utilisateur si authentifié, sinon None.
    """
    try:
        credentials = {
            "email": email,
            "password": password
        }
        response = supabase.auth.sign_in_with_password(credentials)
        user = response.user
        if user:
            return user
        else:
            st.error("Email ou mot de passe invalide.")
            return None
    except Exception as e:
        st.error(f"Erreur lors de la connexion : {e}")
        return None

def get_user_creation_date(user):
    """
    Récupère la date de création du compte utilisateur.
    Retourne un objet datetime en UTC.
    """
    try:
        created_at = user.created_at  # Déjà un objet datetime.datetime
        if created_at.tzinfo is None:
            # Si l'objet datetime n'a pas de timezone, on le définit sur UTC
            created_at = created_at.replace(tzinfo=pytz.UTC)
        else:
            # Sinon, on convertit l'heure en UTC
            created_at = created_at.astimezone(pytz.UTC)
        return created_at
    except Exception as e:
        st.error(f"Erreur lors de la récupération de la date de création : {e}")
        return None

def check_subscription(user_id):
    """
    Vérifie dans la table "subscriptions" s'il existe une ligne pour user_id = userId
    ET un status dans ['active', 'cancel_pending'].
    Retourne les données de l'abonnement si trouvé, sinon False.
    """
    try:
        response = supabase.table('subscriptions')\
            .select('*')\
            .eq('user_id', user_id)\
            .in_('status', ['active', 'cancel_pending'])\
            .single()\
            .execute()
        data = response.data
        if data:
            return data
        else:
            return False
    except Exception as e:
        st.error(f"Erreur lors de la vérification de l'abonnement : {e}")
        return False

def calculate_time_remaining(plan, updated_at):
    """
    Calcule le temps restant de l'abonnement en fonction du plan et de la date de mise à jour.
    Retourne une chaîne de caractères indiquant le temps restant.
    """
    try:
        # Parse la date avec la partie offset (+00:00)
        start_date = datetime.strptime(updated_at, "%Y-%m-%dT%H:%M:%S.%f%z")

        if plan == 'mensuel':
            end_date = start_date + timedelta(days=30)
        elif plan == 'trimestriel':
            end_date = start_date + timedelta(days=90)
        elif plan == 'annuel':
            end_date = start_date + timedelta(days=365)
        else:
            end_date = start_date + timedelta(days=30)  # Valeur par défaut

        now = datetime.utcnow().replace(tzinfo=pytz.UTC)
        diff = end_date - now

        if diff <= timedelta(0):
            return 'Votre abonnement est expiré.'
        else:
            days = diff.days
            return f"Temps restant : {days} jour(s)"
    except Exception as e:
        st.error(f"Erreur lors du calcul du temps restant : {e}")
        return "Erreur de calcul."

# ===================== FORMULAIRE DE CONNEXION ===================
def login():
    st.markdown("<h2>⚽ Connexion à l'application</h2>", unsafe_allow_html=True)
    st.markdown("<p>Veuillez renseigner vos identifiants pour accéder aux prédictions.</p>", unsafe_allow_html=True)

    email = st.text_input("Email")
    password = st.text_input("Mot de passe", type="password")

    if st.button("Se connecter"):
        if email and password:
            user = authenticate_user(email, password)
            if user:
                st.session_state.authenticated = True
                st.session_state.user_id = user.id

                # Vérifier la période d'essai
                created_at = get_user_creation_date(user)
                if created_at:
                    now = datetime.utcnow().replace(tzinfo=pytz.UTC)
                    diff = now - created_at
                    diff_days = diff.days

                    if diff_days < 7:
                        st.session_state.trial_days_remaining = 7 - diff_days
                        st.success(f"Bienvenue! Vous êtes en période d'essai. Il vous reste {st.session_state.trial_days_remaining} jour(s).")
                    else:
                        # Vérifier l'abonnement
                        subscription = check_subscription(user.id)
                        if subscription:
                            st.session_state.subscription = subscription
                            time_remaining = calculate_time_remaining(subscription['plan'], subscription['updated_at'])
                            st.success(f"Bienvenue! Votre abonnement **{subscription['plan']}** est actif.")
                            st.session_state.time_remaining = time_remaining
                        else:
                            st.error("Votre période d'essai est expirée et vous n'avez pas d'abonnement actif.")
                            st.session_state.authenticated = False
                st.rerun()
        else:
            st.error("Veuillez renseigner votre email et votre mot de passe.")

# ===================== AUTHENTIFICATION ET GESTION DE SESSION ===========================
# Initialiser les variables de session
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'user_id' not in st.session_state:
    st.session_state.user_id = None
if 'trial_days_remaining' not in st.session_state:
    st.session_state.trial_days_remaining = 0
if 'subscription' not in st.session_state:
    st.session_state.subscription = None
if 'time_remaining' not in st.session_state:
    st.session_state.time_remaining = ""

# ===================== MAIN APPLICATION ===========================
if not st.session_state.authenticated:
    login()
    st.stop()

# ===================== INTERFACE UTILISATEUR ===========================
st.title("Dashboard")

# Afficher les informations de l'abonnement ou de la période d'essai
if st.session_state.subscription:
    plan = st.session_state.subscription.get('plan', 'Inconnu')
    status = st.session_state.subscription.get('status', 'Inconnu')
    updated_at = st.session_state.subscription.get('updated_at')

    time_remaining = calculate_time_remaining(plan, updated_at)

    st.markdown("### Votre Abonnement")
    st.write(f"**Plan :** {plan}")
    st.write(f"**Statut :** {status}")
    st.write(time_remaining)
elif st.session_state.trial_days_remaining > 0:
    st.markdown("### Période d'Essai")
    st.write(f"Temps restant dans votre période d'essai : {st.session_state.trial_days_remaining} jour(s).")
else:
    st.error("Votre période d'essai est expirée et vous n'avez pas d'abonnement actif.")
    st.stop()

# Afficher le lien vers Streamlit si en trial ou abonnement actif
if st.session_state.subscription or st.session_state.trial_days_remaining > 0:
    # Ici, vous pouvez ajouter un lien ou un bouton pour accéder à d'autres parties de l'application
    # Comme l'application est déjà intégrée dans Streamlit, vous pouvez directement afficher le contenu
    # ou rediriger vers une autre page si nécessaire.
    
    # Exemple de bouton de déconnexion :
    if st.button("Se déconnecter"):
        st.session_state.authenticated = False
        st.session_state.user_id = None
        st.session_state.subscription = None
        st.session_state.trial_days_remaining = 0
        st.session_state.time_remaining = ""
        st.rerun()

# ===================== CONTENU DE L'APPLICATION ===========================
st.markdown("### Analyse des matchs")

# Votre code existant pour l'analyse des matchs
# ...

# Exemple d'utilisation : Générer une analyse IA
# home_team_name, away_team_name, home_prob, draw_prob, away_prob, home_form_score, away_form_score, home_h2h_score, away_h2h_score

# Vous pouvez ajouter un formulaire ou une interface utilisateur pour entrer ces informations


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

# ===================== API FOOTBALL ===============================
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

# ===================== SÉLECTION DE LA DATE =======================
today = date.today()
selected_date = st.date_input(
    "Sélectionnez une date (à partir d'aujourd'hui) :",
    min_value=today,
    value=today
)

# Calcul de la saison
season_year = selected_date.year - 1 if selected_date.month < 8 else selected_date.year

# ===================== SÉLECTION DU CONTINENT =====================
continents = ["Europe", "South America", "North America", "Asia", "Africa"]
selected_continent = st.selectbox("Sélectionnez un continent :", continents)

# ===================== GRANDES COMPÉTITIONS EUROPÉENNES ===========
european_top_competitions = {
    "UEFA Champions League": 2,
    "UEFA Europa League": 3,
    "UEFA Europa Conference League": 848
}

# ===================== RÉCUPERATION DE TOUTES LES LIGUES ==========
response = requests.get(API_URL_LEAGUES, headers=headers)
if response.status_code == 200:
    data_leagues = response.json().get('response', [])
    
    # Extraction de tous les pays
    all_countries = list({
        league['country']['name']
        for league in data_leagues 
        if league.get('country', {}).get('name')
    })
    
    # On réordonne les pays en fonction du continent sélectionné
    all_countries = reorder_countries(selected_continent, all_countries)
    
    # Si le continent est l'Europe, on ajoute "International" en tête 
    if selected_continent == "Europe":
        if "International" not in all_countries:
            all_countries = ["International"] + all_countries
    
    # Sélection du pays
    selected_country = st.selectbox("Sélectionnez un pays :", all_countries)

else:
    st.error("Impossible de récupérer la liste des ligues.")
    selected_country = None
    data_leagues = []

# ===================== CHOIX DE LA COMPÉTITION ====================
league_id = None
league_info = None

if selected_country:
    if selected_continent == "Europe" and selected_country == "International":
        comp_options = list(european_top_competitions.keys())
        selected_league_name = st.selectbox("Sélectionnez une grande compétition européenne :", comp_options)
        league_id = european_top_competitions[selected_league_name]
        league_info = next((l for l in data_leagues if l['league']['id'] == league_id), None)
    else:
        # Récupération de toutes les ligues pour le pays sélectionné
        leagues_in_country = [
            l for l in data_leagues 
            if l['country']['name'] == selected_country
        ]
        
        # Tri alphabétique
        leagues_in_country_sorted = sorted(leagues_in_country, key=lambda x: x['league']['name'])
        
        # Identifie celles considérées comme "D1"
        d1_names = top_leagues_names.get(selected_country, [])
        top_leagues_in_country = [l for l in leagues_in_country_sorted if l['league']['name'] in d1_names]
        other_leagues_in_country = [l for l in leagues_in_country_sorted if l['league']['name'] not in d1_names]
        
        # Fusionne : d'abord la D1, puis le reste
        reordered_leagues = top_leagues_in_country + other_leagues_in_country
        
        # Liste des noms à afficher
        league_names = [l['league']['name'] for l in reordered_leagues]
        
        selected_league_name = st.selectbox("Sélectionnez une compétition :", league_names)
        
        selected_league = next((l for l in reordered_leagues if l['league']['name'] == selected_league_name), None)
        league_id = selected_league['league']['id'] if selected_league else None
        league_info = selected_league

# ===================== LISTE DES MATCHS ===========================
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

API_URL_FIXTURES_H2H = "https://v3.football.api-sports.io/fixtures/headtohead"

def get_h2h_score(home_team_id, away_team_id):
    """Retourne la proportion de victoires domicile et extérieures sur l’historique H2H."""
    params = {'h2h': f"{home_team_id}-{away_team_id}"}
    resp = requests.get(API_URL_FIXTURES_H2H, headers=headers, params=params)
    if resp.status_code == 200:
        h2h_data = resp.json().get('response', [])
        if not h2h_data:
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
        'season': datetime.now().year,  # Correction ici
        'team': team_id
    }
    resp = requests.get('https://v3.football.api-sports.io/injuries', headers=headers, params=injuries_params)
    if resp.status_code == 200:
        injuries_data = resp.json().get('response', [])
        count = len(injuries_data)
        return max(0, 1 - count * 0.05)
    return 0.9


# ===================== NOUVELLE FONCTION GEO AVEC POSITIONSTACK =============
def geocode_city(city_name):
    """
    Géocode un nom de ville via l'API PositionStack.
    Retourne (lat, lon) ou (None, None) en cas d'échec.
    """
    base_url = "http://api.positionstack.com/v1/forward"
    params = {
        "access_key": POSITIONSTACK_API_KEY,
        "query": city_name,
        "limit": 1
    }
    try:
        resp = requests.get(base_url, params=params, timeout=10)
        resp.raise_for_status()  # génère une exception si code HTTP != 200
        data = resp.json()
        
        if "data" in data and len(data["data"]) > 0:
            first_result = data["data"][0]
            lat = first_result.get("latitude")
            lon = first_result.get("longitude")
            if lat is not None and lon is not None:
                return float(lat), float(lon)
        # Si pas de résultat, on renvoie None
        return None, None

    except requests.exceptions.RequestException as e:
        st.error(f"Erreur lors de la requête PositionStack : {e}")
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

# ===================== AFFICHAGE FINAL ============================
if 'match_id' not in st.session_state:
    st.session_state.match_id = None

if league_id and match_id:
    st.session_state.match_id = match_id

if st.session_state.match_id:
    selected_fixture = next(
        (f for f in data_fixtures if f['fixture']['id'] == st.session_state.match_id), 
        None
    )
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

        lat, lon = geocode_city(fixture_city)  # <-- Utilise la nouvelle fonction PositionStack
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

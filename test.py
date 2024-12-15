import streamlit as st
import pandas as pd
import requests
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.ensemble import RandomForestClassifier, VotingClassifier
from sklearn.model_selection import GridSearchCV, train_test_split, StratifiedKFold, cross_val_score
from sklearn.utils import resample
from sklearn.svm import SVC
from sklearn.neural_network import MLPClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import accuracy_score
from sklearn.impute import SimpleImputer
import xgboost as xgb
import lightgbm as lgb
import seaborn as sns
import matplotlib.pyplot as plt
from sklearn.feature_selection import SelectKBest, f_classif, VarianceThreshold

API_KEY = 'aa14874600855457b5a838ec894a06ae'
API_URL_LEAGUES = 'https://v3.football.api-sports.io/leagues'
API_URL_FIXTURES = 'https://v3.football.api-sports.io/fixtures'
API_URL_TEAMS = 'https://v3.football.api-sports.io/teams'
API_URL_STANDINGS = 'https://v3.football.api-sports.io/standings'
API_URL_WEATHER = 'https://my.meteoblue.com/packages/basic-1h'
WEATHER_API_KEY = 'mOpwoft03br5cj7z'

label_encoder = LabelEncoder()

continents = {
    "Europe": ["France", "Germany", "Italy", "Spain", "England"],
    "Asia": ["Japan", "South Korea", "China", "India"],
    "Africa": ["Nigeria", "South Africa", "Egypt", "Morocco"],
    "North America": ["United States", "Canada", "Mexico"],
    "South America": ["Brazil", "Argentina", "Colombia", "Chile"],
    "Oceania": ["Australia", "New Zealand"]
}

def get_leagues(api_key):
    response = requests.get(API_URL_LEAGUES, headers={'x-apisports-key': api_key})
    return pd.json_normalize(response.json().get('response', [])) if response.status_code == 200 else pd.DataFrame()

def get_match_data(api_key, date, league_id, season):
    try:
        response = requests.get(
            API_URL_FIXTURES, 
            headers={'x-apisports-key': api_key}, 
            params={'date': date, 'league': league_id, 'season': 2024}
        )
        response.raise_for_status()
        st.write("Réponse brute de l'API:", response.json())  # Affichez la réponse brute pour le débogage
        matches = response.json().get('response', [])
        if not matches:
            st.warning("Aucune donnée de match trouvée pour la requête API.")
        return pd.json_normalize(matches)
    except requests.exceptions.HTTPError as err:
        st.error(f"Erreur HTTP: {err}")
    except requests.exceptions.RequestException as err:
        st.error(f"Erreur de requête: {err}")
    return pd.DataFrame()  # Cette ligne doit être à l'intérieur de la fonction

def get_historical_data(api_key, league_id, team_id, seasons):
    historical_data = pd.DataFrame()
    for season in seasons:
        response = requests.get(API_URL_FIXTURES, headers={'x-apisports-key': api_key}, params={'league': league_id, 'team': team_id, 'season': season})
        if response.status_code == 200:
            matches = response.json().get('response', [])
            if matches:
                matches_df = pd.json_normalize(matches)
                if not matches_df.empty and matches_df.notna().any(axis=None):
                    historical_data = pd.concat([historical_data, matches_df], ignore_index=True)
    return historical_data

def get_team_logo(api_key, team_id):
    response = requests.get(API_URL_TEAMS, headers={'x-apisports-key': api_key}, params={'id': team_id})
    return response.json().get('response', [{}])[0].get('team', {}).get('logo', '')

def get_recent_performance(api_key, team_id, num_matches=5):
    response = requests.get(API_URL_FIXTURES, headers={'x-apisports-key': api_key}, params={'team': team_id, 'last': num_matches})
    if response.status_code == 200:
        matches = response.json().get('response', [])
        return pd.json_normalize(matches)
    return pd.DataFrame()

def get_player_performance(api_key, team_id, season):
    response = requests.get(f"{API_URL_TEAMS}/{team_id}/players", headers={'x-apisports-key': api_key}, params={'season': season})
    if response.status_code == 200:
        players = response.json().get('response', [])
        return pd.json_normalize(players)
    return pd.DataFrame()

def get_team_standings(api_key, league_id, season):
    response = requests.get(API_URL_STANDINGS, headers={'x-apisports-key': api_key}, params={'league': league_id, 'season': season})
    return pd.json_normalize(response.json().get('response', [{}])[0].get('league', {}).get('standings', [[]])[0]) if response.status_code == 200 else pd.DataFrame()

def get_weather_data(lat, lon, date):
    response = requests.get(
        API_URL_WEATHER,
        params={
            'lat': lat,
            'lon': lon,
            'apikey': WEATHER_API_KEY,
            'timeformat': 'Y-M-D',
            'format': 'json',
            'variables': 'temperature,relativehumidity,windspeed,precipitation'
        }
    )
    if response.status_code == 200:
        data = response.json()
        if 'data_1h' in data:
            return pd.json_normalize(data['data_1h'])
    return pd.DataFrame()

def get_betting_odds(api_key, league_id, match_id):
    API_URL_ODDS = 'https://v3.football.api-sports.io/odds'
    response = requests.get(API_URL_ODDS,
                            headers={'x-apisports-key': api_key},
                            params={'league': league_id, 'fixture': match_id})
    if response.status_code == 200:
        data = response.json().get('response', [])
        if data:
            odds = data[0].get('bookmakers', [])[0].get('bets', [])[0].get('values', [])
            home_odds = next((odd['odd'] for odd in odds if odd['value'] == 'Home'), None)
            draw_odds = next((odd['odd'] for odd in odds if odd['value'] == 'Draw'), None)
            away_odds = next((odd['odd'] for odd in odds if odd['value'] == 'Away'), None)
            return float(home_odds), float(draw_odds), float(away_odds)
    return None, None, None

def prepare_data_with_advanced_features(matches, recent_home, recent_away, player_home, player_away, standings, weather):
    features = matches[['teams.home.id', 'teams.away.id']].apply(label_encoder.fit_transform)

    home_performance = recent_home[['teams.home.id', 'goals.home', 'goals.away']]
    home_performance = home_performance.groupby('teams.home.id').sum().reset_index().rename(columns={'goals.home': 'home_goals_scored', 'goals.away': 'home_goals_conceded'})

    away_performance = recent_away[['teams.away.id', 'goals.away', 'goals.home']]
    away_performance = away_performance.groupby('teams.away.id').sum().reset_index().rename(columns={'goals.away': 'away_goals_scored', 'goals.home': 'away_goals_conceded'})

    # Merge team standings data
    standings = standings[['team.id', 'rank', 'points', 'goalsDiff', 'form', 'status', 'description']].fillna(0)
    features = features.merge(standings, left_on='teams.home.id', right_on='team.id', how='left', suffixes=('', '_home'))
    features = features.merge(standings, left_on='teams.away.id', right_on='team.id', how='left', suffixes=('', '_away'))

    # Add weather data
    if not weather.empty:
        weather_features = weather[['temperature', 'relativehumidity', 'windspeed', 'precipitation']].fillna(0)
        features = features.join(weather_features)

    features = features.merge(home_performance, left_on='teams.home.id', right_on='teams.home.id', how='left').fillna(0)
    features = features.merge(away_performance, left_on='teams.away.id', right_on='teams.away.id', how='left').fillna(0)

    if 'statistics.goals' in player_home.columns and 'statistics.goals' in player_away.columns:
        top_home_player = player_home.nlargest(1, 'statistics.goals')
        top_away_player = player_away.nlargest(1, 'statistics.goals')
        features['home_top_player_goals'] = top_home_player['statistics.goals'].values[0] if not top_home_player.empty else 0
        features['away_top_player_goals'] = top_away_player['statistics.goals'].values[0] if not top_away_player.empty else 0

    features.columns = features.columns.astype(str)

    # Filtrer les colonnes pour ne garder que celles avec des valeurs numériques
    numeric_columns = features.select_dtypes(include=['number']).columns
    features = features[numeric_columns]

    # Ajouter plus de caractéristiques
    features['home_goal_difference'] = features['home_goals_scored'] - features['home_goals_conceded']
    features['away_goal_difference'] = features['away_goals_scored'] - features['away_goals_conceded']

    # Supprimer les caractéristiques avec faible variance
    selector = VarianceThreshold(threshold=0)
    features = selector.fit_transform(features)

    status_mapping = {'FT': 1, 'AET': 2, 'PEN': 3, 'NS': 0}
    labels = matches['fixture.status.short'].map(status_mapping).fillna(0).astype(int)

    features = pd.DataFrame(features)
    features.columns = selector.get_feature_names_out()

    features = features.reset_index(drop=True)
    labels = labels.reset_index(drop=True)

    return features, labels

def train_and_evaluate_model(features, target):
    X_train, X_test, y_train, y_test = train_test_split(features, target, test_size=0.2, random_state=42)

    rf_model = RandomForestClassifier(n_estimators=100, random_state=42)
    xgb_model = xgb.XGBClassifier(random_state=42)
    svc_model = SVC(probability=True, random_state=42)
    mlp_model = MLPClassifier(random_state=42)

    models = [
        ('Random Forest', rf_model),
        ('XGBoost', xgb_model),
        ('Support Vector Machine', svc_model),
        ('MLP Classifier', mlp_model)
    ]

    for name, model in models:
        calibrated_model = CalibratedClassifierCV(model, cv=5)
        calibrated_model.fit(X_train, y_train)
        y_pred = calibrated_model.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)
        st.write(f"Modèle : {name}, Précision : {accuracy:.2f}")

    voting_model = VotingClassifier(estimators=models, voting='soft')
    voting_model.fit(X_train, y_train)
    y_pred_voting = voting_model.predict(X_test)
    accuracy_voting = accuracy_score(y_test, y_pred_voting)
    st.write(f"Modèle d'ensemble (Voting Classifier), Précision : {accuracy_voting:.2f}")

    return voting_model

def get_predictions(api_key, fixture_id):
    API_URL_PREDICTIONS = 'https://v3.football.api-sports.io/predictions'
    response = requests.get(API_URL_PREDICTIONS, headers={'x-apisports-key': api_key}, params={'fixture': fixture_id})
    if response.status_code == 200:
        return response.json().get('response', {})
    else:
        st.error(f"Échec de l'appel API pour les prédictions avec le code de statut: {response.status_code}")
    return {}

def main():
    st.title("Prédictions de Matchs de Football")

    st.write("Sélectionnez le continent, le pays et la date des matchs pour obtenir les prédictions.")

    continent = st.selectbox("Sélectionnez le continent", list(continents.keys()))
    countries = continents[continent]
    country = st.selectbox("Sélectionnez le pays", countries)

    date = st.date_input("Sélectionnez la date des matchs", value=pd.Timestamp('today'), min_value=pd.Timestamp('today'))

    if st.button('Récupérer les matchs du jour'):
        leagues = get_leagues(API_KEY)
        leagues_data = leagues[leagues['country.name'] == country]

        if leagues_data.empty:
            st.error("Aucune ligue trouvée pour le pays sélectionné.")
            return

        league_name = st.selectbox("Sélectionnez la ligue", leagues_data['league.name'])
        league_id = leagues_data[leagues_data['league.name'] == league_name]['league.id'].values[0]

        match_data = get_match_data(API_KEY, date.strftime('%Y-%m-%d'), league_id, "2023")
        if match_data.empty:
            st.warning("Aucune donnée de match trouvée.")
            return

        st.session_state.match_data = match_data
        st.write("Données de match récupérées avec succès.")

    if 'match_data' not in st.session_state:
        st.warning("Aucune donnée de match récupérée. Veuillez récupérer les matchs du jour.")
        return

    match_data = st.session_state.match_data
    match_data['match'] = match_data['teams.home.name'] + " vs " + match_data['teams.away.name'] + " (" + match_data['fixture.date'].astype(str) + ")"
    selected_match = st.selectbox("Sélectionnez un match", match_data['match'])

    if selected_match:
        match_row = match_data[match_data['match'] == selected_match].iloc[0]
        home_team = match_row['teams.home.id']
        away_team = match_row['teams.away.id']
        home_team_name = match_row['teams.home.name']
        away_team_name = match_row['teams.away.name']
        match_id = match_row['fixture.id']

        st.write(f"Match sélectionné: {home_team_name} vs {away_team_name}")

        if st.button('Charger les données pour ce match'):
            with st.spinner('Chargement des données en cours...'):
                recent_home_performance = get_recent_performance(API_KEY, home_team)
                recent_away_performance = get_recent_performance(API_KEY, away_team)
                standings = get_team_standings(API_KEY, league_id, "2023")

            features, labels = prepare_data_with_advanced_features(
                match_data, recent_home_performance, recent_away_performance, pd.DataFrame(), pd.DataFrame(), standings, pd.DataFrame()
            )

            imputer = SimpleImputer(strategy='mean')
            features = pd.DataFrame(imputer.fit_transform(features), columns=features.columns)

            train_features, val_features, train_labels, val_labels = train_test_split(features, labels, test_size=0.33, random_state=42)

            # Convertir les étiquettes en pandas Series
            train_labels_series = pd.Series(train_labels)

            # Compter le nombre d'occurrences de chaque classe
            class_counts = train_labels_series.value_counts()

            # Afficher les classes et leurs comptes
            st.write("Nombre d'occurrences par classe :")
            st.write(class_counts)

            # Déterminer les classes insuffisantes
            min_class_threshold = 2  # Par exemple, on considère qu'une classe est insuffisante si elle a moins de 2 occurrences
            insufficient_classes = class_counts[class_counts < min_class_threshold]

            # Afficher les classes insuffisantes
            st.write("Classes avec un nombre insuffisant d'occurrences :")
            st.write(insufficient_classes)

            # Vérification du nombre de classes dans les données d'entraînement
            if len(train_labels_series.unique()) <= 1:
                st.error("Le nombre de classes dans les données d'entraînement est insuffisant. Veuillez vérifier vos données.")
                return

            best_rf_model = RandomForestClassifier(n_estimators=100, class_weight='balanced', random_state=42)
            best_rf_model.fit(train_features, train_labels)

            min_samples_per_class = max(2, train_labels_series.value_counts().min())

            if min_samples_per_class < 2:
                st.error("Le nombre d'exemples pour certaines classes est insuffisant pour une validation croisée à 2 volets. Veuillez vérifier vos données.")
                return

            calibrated_rf_model = CalibratedClassifierCV(best_rf_model, cv=min_samples_per_class)
            calibrated_rf_model.fit(train_features, train_labels)

            xgb_model = xgb.XGBClassifier(n_estimators=20, max_depth=3, random_state=42)
            calibrated_xgb_model = CalibratedClassifierCV(xgb_model, cv=min_samples_per_class)
            calibrated_xgb_model.fit(train_features, train_labels)

            ensemble_model = VotingClassifier(estimators=[
                ('rf', calibrated_rf_model),
                ('xgb', calibrated_xgb_model)
            ], voting='soft')

            ensemble_model.fit(train_features, train_labels)

            svm_model = SVC(probability=True, class_weight='balanced', random_state=42)
            mlp_model = MLPClassifier(hidden_layer_sizes=(20,), max_iter=500, early_stopping=True, random_state=42)

            cross_val_score(svm_model, features, labels, cv=min_samples_per_class)
            cross_val_score(mlp_model, features, labels, cv=min_samples_per_class)

            svm_model.fit(train_features, train_labels)
            mlp_model.fit(train_features, train_labels)

            ensemble_model = VotingClassifier(estimators=[
                ('rf', best_rf_model),
                ('svm', svm_model),
                ('mlp', mlp_model)
            ], voting='soft')

            ensemble_model.fit(train_features, train_labels)

            label_encoder.fit(standings['team.id'])
            home_team_encoded = label_encoder.transform([home_team])[0]
            away_team_encoded = label_encoder.transform([away_team])[0]

            home_performance_vector = recent_home_performance[recent_home_performance['teams.home.id'] == home_team]
            away_performance_vector = recent_away_performance[recent_away_performance['teams.away.id'] == away_team]

            if home_performance_vector.empty or away_performance_vector.empty:
                st.error("Les performances récentes des équipes ne sont pas disponibles.")
                return

            home_performance_vector = home_performance_vector.iloc[0]
            away_performance_vector = away_performance_vector.iloc[0]

            prediction_data = {
                "teams.home.id": home_team_encoded,
                "teams.away.id": away_team_encoded,
                "home_goals_scored": home_performance_vector['goals.home'],
                "home_goals_conceded": home_performance_vector['goals.away'],
                "away_goals_scored": away_performance_vector['goals.away'],
                "away_goals_conceded": away_performance_vector['goals.home'],
                "home_top_player_goals": 0,
                "away_top_player_goals": 0,
                "recent_home_win_rate": home_performance_vector['goals.home'] / (home_performance_vector['goals.home'] + home_performance_vector['goals.away'] + 1),
                "recent_away_win_rate": away_performance_vector['goals.away'] / (away_performance_vector['goals.away'] + away_performance_vector['goals.home'] + 1)
            }

            prediction_features = pd.DataFrame([prediction_data])

            required_columns = features.columns
            for col in required_columns:
                if col not in prediction_features:
                    prediction_features[col] = 0

            prediction_features = prediction_features[required_columns]

            prediction = ensemble_model.predict(prediction_features)
            probability = ensemble_model.predict_proba(prediction_features)

            prob_victory_home = probability[0][0] if len(probability[0]) > 0 else 0
            prob_draw = probability[0][1] if len(probability[0]) > 1 else 0
            prob_victory_away = probability[0][2] if len(probability[0]) > 2 else 0

            st.success("Calcul terminé ! Voici les probabilités :")
            st.write(f"**Prédiction**: {'Victoire de l\'équipe à domicile' if prediction[0] == 0 else ('Match nul' if prediction[0] == 1 else 'Victoire de l\'équipe à l\'extérieur')}")
            st.write(f"**Probabilité de victoire de l'équipe à domicile ({home_team_name})**: {prob_victory_home * 100:.2f}%")
            st.write(f"**Probabilité de match nul**: {prob_draw * 100:.2f}%")
            st.write(f"**Probabilité de victoire de l'équipe à l'extérieur ({away_team_name})**: {prob_victory_away * 100:.2f}%")

            # Récupérer les prédictions API Football
            predictions = get_predictions(API_KEY, match_id)
            if predictions:
                st.write("**Prédictions API Football**")
                st.write(predictions)

if __name__ == '__main__':
    main()

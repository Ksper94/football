import streamlit as st
import pandas as pd
import requests
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.ensemble import RandomForestClassifier, VotingClassifier
from sklearn.model_selection import GridSearchCV, train_test_split, StratifiedKFold
from sklearn.utils import resample
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
WEATHER_API_KEY = 'mOpwoft03br5cj7z'  # Utilise ta clé API

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
    response = requests.get(API_URL_FIXTURES, headers={'x-apisports-key': api_key}, params={'date': date, 'league': league_id, 'season': season})
    return pd.json_normalize(response.json().get('response', [])) if response.status_code == 200 else pd.DataFrame()

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

    # Ajouter plus de caractéristiques pertinentes
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

    return features, labels, home_performance, away_performance

def balance_classes(features, labels):
    majority_size = labels.value_counts().max()

    balanced_features = pd.DataFrame()
    balanced_labels = pd.Series(dtype=int)

    for label in labels.unique():
        features_class = features[labels == label]
        labels_class = labels[labels == label]
        
        features_resampled, labels_resampled = resample(features_class, labels_class,
                                                        replace=True,
                                                        n_samples=majority_size,
                                                        random_state=42)
        
        balanced_features = pd.concat([balanced_features, features_resampled])
        balanced_labels = pd.concat([balanced_labels, labels_resampled])
    
    return balanced_features, balanced_labels

def show_home_page():
    st.title("Prédictions des Matchs de Football")
    date = st.date_input("Sélectionnez la date des matchs", value=pd.Timestamp('today'))
    continent = st.selectbox("Sélectionnez le continent", list(continents.keys()))
    countries = continents[continent]
    country = st.selectbox("Sélectionnez le pays", countries)
    
    leagues_data = get_leagues(API_KEY)
    leagues_data = leagues_data[leagues_data['country.name'] == country]
    league_name = st.selectbox("Sélectionnez la ligue", leagues_data['league.name'])
    league_id = leagues_data[leagues_data['league.name'] == league_name]['league.id'].values[0]
    
    current_year = pd.Timestamp('today').year
    seasons = list(range(current_year, current_year - 2, -1))

    if st.button('Récupérer les matchs du jour'):
        match_data = get_match_data(API_KEY, date.strftime('%Y-%m-%d'), league_id, seasons[0])
        st.session_state.match_data = match_data

    # Vérification de match_data dans la session
    if 'match_data' not in st.session_state:
        st.warning("Aucune donnée de match récupérée. Veuillez récupérer les matchs du jour.")
        return

    match_data = st.session_state.match_data

    if not match_data.empty:
        st.write(f"Nombre de matchs récupérés: {len(match_data)}")
        match_data['match'] = match_data['teams.home.name'] + " vs " + match_data['teams.away.name'] + " (" + match_data['fixture.date'].astype(str) + ")"
        selected_match = st.selectbox("Sélectionnez un match", match_data['match'])

        if selected_match:
            match_row = match_data[match_data['match'] == selected_match].iloc[0]
            home_team = match_row['teams.home.id']
            away_team = match_row['teams.away.id']
            home_team_name = match_row['teams.home.name']
            away_team_name = match_row['teams.away.name']

            st.write(f"Match sélectionné: {home_team_name} vs {away_team_name}")
            
            # Afficher les logos des équipes
            home_team_logo = get_team_logo(API_KEY, home_team)
            away_team_logo = get_team_logo(API_KEY, away_team)
            st.image(home_team_logo, caption=f"Logo de {home_team_name}")
            st.image(away_team_logo, caption=f"Logo de {away_team_name}")

            if st.button('Charger les données pour ce match'):
                historical_data_home = get_historical_data(API_KEY, league_id, home_team, seasons)
                historical_data_away = get_historical_data(API_KEY, league_id, away_team, seasons)
                
                # Ajouter les performances récentes
                recent_home_performance = get_recent_performance(API_KEY, home_team, 5)
                recent_away_performance = get_recent_performance(API_KEY, away_team, 5)
                
                # Ajouter les performances des joueurs clés
                player_home_performance = get_player_performance(API_KEY, home_team, seasons[0])
                player_away_performance = get_player_performance(API_KEY, away_team, seasons[0])

                all_matches = pd.concat([historical_data_home, historical_data_away])

                # Ajouter les données de classement
                standings = get_team_standings(API_KEY, league_id, seasons[0])
                
                # Ajouter les données météorologiques (fournir la latitude et la longitude)
                weather = get_weather_data(lat=48.8566, lon=2.3522, date=date.strftime('%Y-%m-%d'))

                features, labels, home_performance, away_performance = prepare_data_with_advanced_features(
                    all_matches, recent_home_performance, recent_away_performance, 
                    player_home_performance, player_away_performance, standings, weather
                )

                # Supprimer les caractéristiques hautement corrélées
                threshold = 0.95
                corr_features = set()
                for i in range(len(features.columns)):
                    for j in range(i):
                        if abs(features.iloc[i, j]) > threshold:
                            colname = features.columns[i]
                            corr_features.add(colname)

                features_reduced = features.drop(columns=corr_features)

                # Équilibrer manuellement les classes
                features_resampled, labels_resampled = balance_classes(features_reduced, labels)

                # Utiliser LGBMClassifier pour optimiser les hyperparamètres et gérer l'arrêt anticipé
                lgb_model = lgb.LGBMClassifier(
                    learning_rate=0.1,
                    num_leaves=31,
                    min_data_in_leaf=20,
                    objective='binary',
                    metric='binary_logloss',
                    n_estimators=1000
                )

                train_features, val_features, train_labels, val_labels = train_test_split(features_resampled, labels_resampled, test_size=0.2, random_state=42)

                lgb_model.fit(
                    train_features,
                    train_labels,
                    eval_set=[(val_features, val_labels)],
                    eval_metric='logloss',
                    callbacks=[lgb.early_stopping(10)]
                )

                best_lgb_model = lgb_model

                home_team_encoded = label_encoder.transform([home_team])[0]
                away_team_encoded = label_encoder.transform([away_team])[0]

                # Construire le vecteur de caractéristiques pour la prédiction
                home_performance_vector = home_performance[home_performance['teams.home.id'] == home_team]
                away_performance_vector = away_performance[away_performance['teams.away.id'] == away_team]

                if home_performance_vector.empty or away_performance_vector.empty:
                    st.error("Les performances récentes des équipes ne sont pas disponibles.")
                    return

                home_performance_vector = home_performance_vector.iloc[0]
                away_performance_vector = away_performance_vector.iloc[0]

                # Utiliser seulement les colonnes qui correspondent aux features_reduced
                prediction_data = {
                    "teams.home.id": home_team_encoded,
                    "teams.away.id": away_team_encoded,
                    "home_goals_scored": home_performance_vector['home_goals_scored'],
                    "home_goals_conceded": home_performance_vector['home_goals_conceded'],
                    "away_goals_scored": away_performance_vector['away_goals_scored'],
                    "away_goals_conceded": away_performance_vector['away_goals_conceded'],
                    "home_top_player_goals": player_home_performance['statistics.goals'].max() if 'statistics.goals' in player_home_performance.columns else 0,
                    "away_top_player_goals": player_away_performance['statistics.goals'].max() if 'statistics.goals' in player_away_performance.columns else 0
                }

                prediction_features = pd.DataFrame([prediction_data])

                # Assurer que les colonnes de prédiction correspondent
                prediction_features = prediction_features[features_reduced.columns]

                prediction = best_lgb_model.predict(prediction_features)
                probability = best_lgb_model.predict_proba(prediction_features)

                st.write(f"**Prédiction**: {'Victoire de l\'équipe à domicile' if prediction[0] == 1 else ('Match nul' if prediction[0] == 2 else 'Victoire de l\'équipe à l\'extérieur')}")

                # Affichage des probabilités, en assurant que chaque classe est présente
                prob_victory_home = probability[0][1] if len(probability[0]) > 1 else 0
                prob_draw = probability[0][2] if len(probability[0]) > 2 else 0
                prob_victory_away = probability[0][0] if len(probability[0]) > 0 else 0

                st.write(f"**Probabilité de victoire de l'équipe à domicile**: {prob_victory_home * 100:.2f}%")
                st.write(f"**Probabilité de match nul**: {prob_draw * 100:.2f}%")
                st.write(f"**Probabilité de victoire de l'équipe à l'extérieur**: {prob_victory_away * 100:.2f}%")

if __name__ == '__main__':
    show_home_page()

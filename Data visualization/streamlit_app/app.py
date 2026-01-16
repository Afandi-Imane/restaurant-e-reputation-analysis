import streamlit as st
import pandas as pd
import plotly.express as px

# --- Configuration de la page ---
st.set_page_config(
    page_title="Restaurant Insights Dashboard",
    page_icon="🍔",
    layout="wide"
)

# --- Chargement et nettoyage des données principales ---
@st.cache_data
def load_main_data(file_path):
    df = pd.read_excel(file_path)
    df.columns = df.columns.str.strip()
    for col in ['Latitude', 'Longitude', 'sentiment']:
        if df[col].dtype == 'object':
            df[col] = df[col].str.replace(',', '.', regex=False)
        df[col] = pd.to_numeric(df[col], errors='coerce')
    df['Date'] = pd.to_datetime(df['Date'], dayfirst=True, errors='coerce')
    df['Annee'] = df['Date'].dt.year
    df['Prix moyen (MAD)'] = pd.to_numeric(df['Prix moyen (MAD)'], errors='coerce')
    df['nbr_étoile'] = pd.to_numeric(df['nbr_étoile'], errors='coerce')
    df.dropna(subset=['Latitude', 'Longitude', 'Date', 'Annee', 'sentiment', 'nbr_étoile', 'Prix moyen (MAD)'], inplace=True)
    df['Annee'] = df['Annee'].astype(int)
    return df

# --- Chargement des données de fréquence ---
@st.cache_data
def load_frequency_data(file_path):
    try:
        df_freq = pd.read_excel(file_path)
        df_freq.columns = df_freq.columns.str.strip() # Nettoyer les noms de colonnes

        # Colonnes attendues dans le fichier source
        expected_cols_in_file = ['restaurant', 'ville', 'expression', 'frequence']
        actual_cols = df_freq.columns.tolist()

        col_mapping = {}
        # Vérifier la présence des colonnes attendues, en ignorant la casse et les espaces
        for expected_col in expected_cols_in_file:
            found = False
            for actual_col in actual_cols:
                if actual_col.strip().lower() == expected_col.strip().lower():
                    col_mapping[expected_col] = actual_col # Stocker le mapping du nom trouvé au nom attendu
                    found = True
                    break
            if not found:
                st.error(f"Colonne attendue '{expected_col}' introuvable dans le fichier de fréquences '{file_path}'. Vérifiez les en-têtes.")
                return pd.DataFrame()

        # Définir le mapping final vers les noms standards utilisés dans le reste du code
        standard_rename_map = {
            'restaurant': 'Nom du Restaurant',
            'ville': 'Ville', # Nouvelle colonne à mapper
            'expression': 'Expression',
            'frequence': 'Frequence'
        }
        
        # Renommer les colonnes en utilisant le mapping trouvé et les noms standards
        # Assurez-vous que toutes les colonnes attendues ont été trouvées pour éviter des erreurs
        if len(col_mapping) == len(expected_cols_in_file):
            df_freq.rename(columns={col_mapping[key]: standard_rename_map[key] for key in col_mapping}, inplace=True)
        else:
            # Si une colonne n'a pas été trouvée, on ne procède pas au renommage.
            # Le message d'erreur précédent devrait déjà avoir arrêté l'exécution.
            return pd.DataFrame()

        # Colonnes requises SPÉCIFIQUEMENT pour le graphique de fréquence (après renommage)
        required_cols_for_plotting = ['Expression', 'Frequence']
        # Colonnes requises pour le filtrage par restaurant (après renommage)
        required_cols_for_filtering = ['Nom du Restaurant', 'Expression', 'Frequence']

        # Vérifier que les colonnes nécessaires au plotting et au filtrage sont bien présentes
        if not all(col in df_freq.columns for col in required_cols_for_plotting):
             st.error(f"Colonnes nécessaires pour le graphique manquantes après renommage. Attendu : {', '.join(required_cols_for_plotting)}. Trouvé : {df_freq.columns.tolist()}")
             return pd.DataFrame()
        if not all(col in df_freq.columns for col in required_cols_for_filtering):
             # Ce cas est moins critique pour l'affichage du graphique, mais bon à vérifier
             st.warning(f"Colonnes nécessaires pour le filtrage par restaurant manquantes après renommage. Attendu : {', '.join(required_cols_for_filtering)}. Trouvé : {df_freq.columns.tolist()}")
             # On continue quand même car le graphique peut fonctionner sans le filtrage parfait

        # Convertir la colonne 'Frequence' en numérique, en gérant les erreurs
        df_freq['Frequence'] = pd.to_numeric(df_freq['Frequence'], errors='coerce')
        df_freq.dropna(subset=['Frequence'], inplace=True) # Supprimer les lignes où la fréquence n'a pas pu être convertie

        return df_freq
    except FileNotFoundError:
        st.warning(f"Fichier de fréquences '{file_path}' non trouvé. Impossible d'afficher les fréquences.")
        return pd.DataFrame()
    except Exception as e:
        st.warning(f"Erreur lors du chargement du fichier de fréquences '{file_path}' : {e}")
        return pd.DataFrame()

# --- Chargement des données ---
df_main = load_main_data('All cities Data.xlsx')
# Assurez-vous que ce fichier est dans le même répertoire que votre script Streamlit
frequency_file_name ='expressions.xlsx'
df_freq_all = load_frequency_data(frequency_file_name)

# --- Table de synthèse enrichie pour la carte ---
@st.cache_data
def create_summary_table(_df):
    df_restaurant_summary = _df.groupby('Nom du Restaurant').agg(
        ÉtoilesMoyennes=('nbr_étoile', 'mean'),
        ville=('ville', 'first'),
        PrixMoyen=('Prix moyen (MAD)', 'first'),
        Adresse=('Adresse', 'first'),
        IntervallePrix=('Intervalle (MAD)', 'first'),
        Latitude=('Latitude', 'first'),
        Longitude=('Longitude', 'first')
    ).reset_index()
    return df_restaurant_summary

df_summary = create_summary_table(df_main)

# --- Barre latérale pour les filtres généraux ---
st.sidebar.header("Filtres Généraux")
ville = st.sidebar.multiselect("Sélectionner la Ville :", options=sorted(df_summary["ville"].unique()), default=sorted(df_summary["ville"].unique()))
etoiles = st.sidebar.slider("Sélectionner la note MOYENNE :", min_value=0.0, max_value=5.0, value=(0.0, 5.0), step=0.1, format="%.1f")
prix = st.sidebar.slider("Sélectionner le prix (MAD) :", min_value=int(df_summary["PrixMoyen"].min()), max_value=int(df_summary["PrixMoyen"].max()), value=(int(df_summary["PrixMoyen"].min()), int(df_summary["PrixMoyen"].max())))

# --- Logique de filtrage ---
df_summary_selection = df_summary.query("ville == @ville and ÉtoilesMoyennes >= @etoiles[0] and ÉtoilesMoyennes <= @etoiles[1] and PrixMoyen >= @prix[0] and PrixMoyen <= @prix[1]")
restaurants_selectionnes = df_summary_selection['Nom du Restaurant'].unique()

# --- Page principale ---
st.title("Restaurant Insights Dashboard")
st.markdown("---")
st.header("Analyse Détaillée")

liste_options_resto = ["Tous les restaurants"] + sorted(list(restaurants_selectionnes))
restaurant_specifique = st.selectbox("Pour voir le détail, sélectionnez un restaurant :", options=liste_options_resto)

# --- Logique de filtrage final ---
if restaurant_specifique != "Tous les restaurants":
    df_map_selection = df_summary_selection[df_summary_selection["Nom du Restaurant"] == restaurant_specifique]
    df_final_selection = df_main[df_main["Nom du Restaurant"] == restaurant_specifique]
else:
    df_map_selection = df_summary_selection.copy()
    df_final_selection = df_main[df_main['Nom du Restaurant'].isin(restaurants_selectionnes)]

# --- Affichage dynamique ---
if df_final_selection.empty:
    st.warning("Aucune donnée disponible pour les filtres sélectionnés.")
    st.stop()

if restaurant_specifique != "Tous les restaurants":
    titre_kpi = f"Données pour : {restaurant_specifique}"
else:
    titre_kpi = f"{len(restaurants_selectionnes)} restaurants correspondent aux filtres"
st.subheader(titre_kpi)

# --- KPIs ---
score_moyen_sentiment = round(df_final_selection["sentiment"].mean(), 2)
note_moyenne = round(df_final_selection["nbr_étoile"].mean(), 2)
kpi1, kpi2 = st.columns(2)
kpi1.metric(label="Note Moyenne (sur 5)", value=f"{note_moyenne:.2f} ⭐")
kpi2.metric(label="Score Moyen de Sentiment", value=score_moyen_sentiment)
st.markdown("---")

# --- Graphiques ---

# --- Ligne 1 : Carte (col_map) et Sentiment (col_sentiment) ---
col_map, _ = st.columns([5, 0.1])  # Carte prend 2/5 de la largeur, Sentiment 3/5

with col_map: # Colonne pour la carte
    st.subheader("Localisation")
    fig_map = px.scatter_mapbox(
        df_map_selection, lat="Latitude", lon="Longitude",
        zoom=5 if restaurant_specifique == "Tous les restaurants" else 15,
        color="ÉtoilesMoyennes", color_continuous_scale="RdYlGn",
        range_color=[1, 5], hover_name="Nom du Restaurant",
        hover_data={
            'Adresse': True, 'IntervallePrix': True,
            'ÉtoilesMoyennes': ':.2f', 'Latitude': False, 'Longitude': False
        }
    )
    fig_map.update_traces(marker_size=20)
    fig_map.update_layout(
        mapbox_style="open-street-map",
        mapbox_center={"lat": df_map_selection['Latitude'].mean(), "lon": df_map_selection['Longitude'].mean()}
    )
    st.plotly_chart(fig_map, use_container_width=True)


# --- Ligne 2 : Donut (col_donut) et Fréquence (col_freq) ---
col_donut, col_freq = st.columns([2, 3]) # On garde la même proportion pour la cohérence

with col_donut: # Colonne pour le graphique donut
    st.subheader("Répartition des avis par note")
    repartition_notes = df_final_selection['nbr_étoile'].value_counts().reset_index()
    repartition_notes.columns = ['Note', 'Nombre d\'avis']
    fig_donut = px.pie(
        repartition_notes, names='Note', values='Nombre d\'avis',
        hole=0.5,
        color_discrete_map={5: '#6E4228', 4: '#A55D35', 1: '#FCE4D6', 3: '#D9825A', 2: '#F5B799'}
    )
    fig_donut.update_traces(textposition='outside', textinfo='percent+label', pull=[0.05, 0, 0, 0, 0])
    fig_donut.update_layout(showlegend=False)
    st.plotly_chart(fig_donut, use_container_width=True)

with col_freq: # Colonne pour la fréquence des mots/expressions
    st.subheader("Fréquence des mots/expressions clés")

    df_frequence_mots = pd.DataFrame() # Initialiser un DataFrame vide

    if not df_freq_all.empty:
        if restaurant_specifique == "Tous les restaurants":
            # Si tous les restaurants sont sélectionnés, on agrège les fréquences par expression
            df_frequence_mots = df_freq_all.groupby('Expression')['Frequence'].sum().reset_index()
            df_frequence_mots = df_frequence_mots.sort_values(by='Frequence', ascending=False).head(18)
        else:
            # Si un restaurant spécifique est sélectionné, on filtre les données de fréquence
            # par ce restaurant.
            df_frequence_mots = df_freq_all[df_freq_all['Nom du Restaurant'] == restaurant_specifique]
            df_frequence_mots = df_frequence_mots[['Expression', 'Frequence']]
            df_frequence_mots = df_frequence_mots.sort_values(by='Frequence', ascending=False).head(18)

    if not df_frequence_mots.empty:
        # Calculer une hauteur appropriée pour le graphique de fréquence
        num_expressions = len(df_frequence_mots)
        # Hauteur entre 400px et 800px, s'adapte au nombre d'expressions
        graph_height = min(max(400, num_expressions * 25), 800) 

        fig_frequence = px.bar(
            df_frequence_mots,
            x='Frequence',
            y='Expression',
            orientation='h',
            labels={'Frequence': 'Fréquence', 'Expression': 'Mot/Expression'},
            #title="Fréquence des mots/expressions clés dans les avis",
            height=graph_height
        )
        
        # Ajuster la taille de la police pour les labels de l'axe Y et les titres
        fig_frequence.update_layout(
            yaxis=dict(
                categoryorder='total ascending', # S'assurer que le tri est par fréquence
                tickfont=dict(size=11),          # Taille des labels de l'axe Y (expressions)
                title_font=dict(size=12)         # Taille du titre de l'axe Y
            ),
            xaxis=dict(
                title_font=dict(size=12),        # Taille du titre de l'axe X
                tickfont=dict(size=10)           # Taille des labels de l'axe X (fréquence)
            ),
            #title_font_size=14 # Taille du titre du graphique
        )
        
        st.plotly_chart(fig_frequence, use_container_width=True)
    else:
        st.info("Aucune donnée de fréquence disponible pour l'affichage (vérifiez le fichier de fréquences et les filtres).")


# --- Graphique Évolution de la note moyenne ---
# Ce graphique est placé sous les deux lignes de graphiques principaux.
# --- Ligne 3 : Comparaison des évolutions (Sentiment vs Étoiles) ---
col_sentiment, col_etoiles = st.columns(2)

with col_sentiment:
    st.subheader("Évolution des sentiments par année")
    sentiment_par_annee = df_final_selection.groupby('Annee')['sentiment'].agg(['max', 'mean', 'min']).reset_index()
    sentiment_par_annee = sentiment_par_annee.rename(columns={'mean': 'Moyenne', 'max': 'Max', 'min': 'Min'})
    fig_sentiment = px.line(sentiment_par_annee, x='Annee', y=['Max', 'Moyenne', 'Min'], markers=True)
    st.plotly_chart(fig_sentiment, use_container_width=True)

with col_etoiles:
    st.subheader("Évolution de la note moyenne par année")
    etoiles_par_annee = df_final_selection.groupby('Annee')['nbr_étoile'].mean().reset_index()
    fig_etoiles = px.line(
        etoiles_par_annee, x='Annee', y='nbr_étoile', markers=True,
        labels={"nbr_étoile": "Moyenne des étoiles"}
    )
    fig_etoiles.update_layout(yaxis=dict(range=[0, 5.2]))
    st.plotly_chart(fig_etoiles, use_container_width=True)


# --- Affichage de la liste des restaurants ou des commentaires ---
if restaurant_specifique == "Tous les restaurants":
    st.subheader("Liste des Restaurants Filtrés")
    display_df = df_summary_selection[[
        'Nom du Restaurant', 'ville', 'Adresse', 'ÉtoilesMoyennes', 'IntervallePrix'
    ]].rename(columns={
        'ville': 'Ville', 'ÉtoilesMoyennes': 'Note Moyenne', 'IntervallePrix': 'Fourchette de Prix'
    })
    display_df['Note Moyenne'] = display_df['Note Moyenne'].map('{:.2f}'.format)
    st.dataframe(display_df, use_container_width=True)
else:
    st.subheader(f"Commentaires pour {restaurant_specifique}")
    st.dataframe(df_final_selection[['Date', 'nbr_étoile', 'Commentaire']].sort_values(by='Date', ascending=False))
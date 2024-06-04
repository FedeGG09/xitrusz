import streamlit as st
import pandas as pd
import re
import openai
from rdflib import Graph, RDF, OWL, RDFS, XSD
from rdflib import Namespace
import sqlite3
from sqlite3 import Error
import os
from decouple import config

# Configuración de OpenAI
openai.api_key = (config("API_KEY"))
print(config("API_KEY"))

# CSS personalizado para la interfaz
css = """
<style>
/* Botón naranja */
.btn-neon {
  background-color: #f36f21;
  color: #fff;
  padding: 10px 20px;
  border-radius: 5px;
  font-weight: bold;
  text-transform: uppercase;
  cursor: pointer;
  box-shadow: 0 0 20px #f36f21;
  transition: transform 0.2s;
}

.btn-neon:hover {
  transform: scale(1.05);
}

/* Barra de progreso */
.progress {
  width: 100%;
  height: 20px;
  background-color: #ddd;
  border-radius: 10px;
}

.progress-1 {
  width: 70%;
  background-color: #f36f21;
  border-radius: 10px;
}

/* Chat box */
.chat-box {
  margin: auto;
  max-width: 800px;
  padding: 20px;
  border: 1px solid #ccc;
  border-radius: 10px;
  box-shadow: 0 0 20px rgba(0, 0, 0, 0.1);
}

.user-message {
  background-color: #f36f21;
  color: #fff;
  padding: 10px;
  border-radius: 5px;
  margin-bottom: 10px;
}

.bot-message {
  background-color: #ddd;
  color: #333;
  padding: 10px;
  border-radius: 5px;
  margin-bottom: 10px;
}

.user-icon,
.bot-icon {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  display: inline-block;
  margin-right: 10px;
}

.user-icon {
  background-color: #f36f21;
}

.bot-icon {
  background-color: #ddd;
}
</style>
"""

st.markdown(css, unsafe_allow_html=True)

# Function to read the Excel file
def load_excel_file(file_path):
    df = pd.read_excel(file_path)
    return df

# Function to create RDF ontology from DataFrame
def create_ontology(dataframe):
    g = Graph()
    my_ns = Namespace("http://example.org/")
    for column in dataframe.columns:
        predicate_uri = my_ns["has_" + re.sub(r'\W+', '_', column.lower())]
        g.add((predicate_uri, RDF.type, OWL.DatatypeProperty))
        g.add((predicate_uri, RDFS.domain, my_ns["Table"]))
        g.add((predicate_uri, RDFS.range, XSD.string))
    return g

# Function to extract knowledge dictionary from ontology
def extract_knowledge_dictionary(ontology):
    knowledge_dict = {}
    for s, p, o in ontology:
        if p == RDF.type and o == OWL.DatatypeProperty:
            column_name = re.sub(r'^.*has_', '', s)
            knowledge_dict[column_name] = []
    return knowledge_dict

# Function to split text into chunks
def split_text_into_chunks(dataframe):
    text_chunks = dataframe.values.flatten().tolist()
    return text_chunks

def generate_response(input_text, data):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4-turbo",
            messages=[
                {
                    "role": "user",
                    "content": f"{data}\n\n{input_text}",
                }
            ],
            max_tokens=2000,
            n=1,
            stop=None,
            temperature=0.7,
        )
        if response.choices and len(response.choices) > 0:
            return response.choices[0]['message']['content'].strip()
        else:
            return "Lo siento, no pude generar una respuesta para tu pregunta."
    except openai.error.OpenAIError as e:  # Updated exception handling
        return f"Ocurrió un error al procesar la respuesta de OpenAI: {str(e)}"
    except Exception as e:
        return f"Ocurrió un error inesperado: {str(e)}"

# Function to create a SQLite connection
def create_connection(db_file):
    """ create a database connection to a SQLite database """
    conn = None
    try:
        conn = sqlite3.connect(db_file)
        return conn
    except Error as e:
        st.error(e)
    return conn

# Function to save DataFrame to SQLite
def save_to_sqlite(dataframe, conn, table_name):
    try:
        dataframe.to_sql(table_name, conn, if_exists='replace', index=False)
    except Error as e:
        st.error(e)

# Function to load DataFrame from SQLite
def load_from_sqlite(conn, table_name):
    try:
        df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
        return df
    except Error as e:
        st.error(e)
        return None

# Interacción con Streamlit
def main():
    st.title("Generador de Ontologías y Respuestas")
    
    st.sidebar.header("Menú")
    selected_option = st.sidebar.selectbox("Bases de Datos", options=["Seleccione una base de datos", "Nueva Base de Datos", "Ver Bases de Datos Cargadas"])
    
    if selected_option == "Nueva Base de Datos":
        st.sidebar.subheader("Cargar Nueva Base de Datos")
        file_path = st.sidebar.file_uploader("Cargar archivo Excel", type=["xlsx"], key="file_uploader")
        if file_path is not None:
            new_db_name = st.sidebar.text_input("Nombre de la base de datos:")
            if new_db_name:
                conn = create_connection(f"{new_db_name}.db")
                if conn:
                    df = load_excel_file(file_path)
                    if df is not None:
                        save_to_sqlite(df, conn, new_db_name)
                        st.sidebar.success(f"{new_db_name}.db creada y datos guardados")
    
    elif selected_option == "Ver Bases de Datos Cargadas":
        st.sidebar.subheader("Bases de Datos Cargadas")
        db_files = [f.split(".db")[0] for f in os.listdir() if f.endswith(".db")]
        if db_files:
            selected_db = st.sidebar.selectbox("Seleccione una base de datos para cargar:", db_files)
            if selected_db:
                st.session_state['selected_db'] = selected_db
                st.session_state['db_conn'] = create_connection(f"{selected_db}.db")
                if st.session_state['db_conn']:
                    df = load_from_sqlite(st.session_state['db_conn'], selected_db)
                    if df is not None:
                        st.write("Vista previa de la base de datos cargada:")
                        st.write(df)
                        
                        ontology = create_ontology(df)
                        knowledge_dict = extract_knowledge_dictionary(ontology)
                        text_chunks = split_text_into_chunks(df)
                        
                        st.header("Haz una pregunta:")
                        question_container = st.container()
                        with question_container:
                            user_question = st.text_input("Pregunta:", key="user_question_input", max_chars=200, help="Haz una pregunta sobre los datos cargados.")
                        
                        if user_question:
                            with st.spinner("Procesando respuesta..."):
                                response = generate_response(user_question, data=text_chunks)
                                if "Ocurrió un error" in response:
                                    st.error(response)
                                else:
                                    st.write("Respuesta:")
                                    st.write(response)
        else:
            st.sidebar.write("No hay bases de datos cargadas.")

if __name__ == '__main__':
    main()
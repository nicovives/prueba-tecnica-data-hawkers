import streamlit as st
import pandas as pd
import json
import numpy as np
import matplotlib.pyplot as plt
import plotly.express as px

st.set_page_config(page_title="Cuadro de Mandos - Ventas", layout="wide")

st.title("📊 Dashboard")
st.markdown("Análisis de recurrencia, ingresos por año-mes y distribución geográfica.")

@st.cache_data
def cargar_y_preparar_datos(ruta_archivo):
    datos_crudos = []
    with open(ruta_archivo, 'r', encoding='utf-8') as archivo:
        for linea in archivo:
            datos_crudos.append(json.loads(linea))
            
    df = pd.json_normalize(datos_crudos, record_path='order_items', 
                           meta=['order_id', 'order_date', 'first_name', 'last_name', 
                                 'gender', 'email', 'phone', 'state', 'zip'])
    
    # Parseo
    df['price'] = pd.to_numeric(df['price'])
    df['qty_ordered'] = pd.to_numeric(df['qty_ordered'])
    df['discount_amount'] = pd.to_numeric(df['discount_amount'])
    df['order_date'] = pd.to_datetime(df['order_date'], format='%d-%m-%Y')
    df['total_linea'] = (df['price'] * df['qty_ordered']) - df['discount_amount']
    
    # Eliminar duplicados (asumiendo Opción A)
    df = df.drop_duplicates()
    
    # --- FASE 3: Agrupación por pedidos y clientes ---
    df_pedidos = df.groupby(['order_id', 'order_date', 'email', 'state'], as_index=False)['total_linea'].sum().rename(columns={'total_linea': 'importe_pedido'})
    df_pedidos = df_pedidos.sort_values(['email', 'order_date'])
    df_pedidos['num_pedido'] = df_pedidos.groupby('email').cumcount() + 1
    df_pedidos['tipo_pedido'] = np.where(df_pedidos['num_pedido'] == 1, 'Primer Pedido', 'Recurrente')
    df_pedidos['fecha_adquisicion'] = df_pedidos.groupby('email')['order_date'].transform('min')
    df_pedidos['cohorte_adquisicion'] = df_pedidos['fecha_adquisicion'].dt.to_period('M').astype(str)
    df_pedidos['dias_desde_anterior'] = df_pedidos.groupby('email')['order_date'].diff().dt.days
    
    # --- FASE 4: Funciones de resumen ---
    def crear_tabla_kpis(df_agrupado, dimension):
        resumen = df_agrupado.groupby(dimension).apply(lambda x: pd.Series({
            'Clientes Adquiridos': x['email'].nunique(),
            'Clientes Recurrentes': x[x['tipo_pedido'] == 'Recurrente']['email'].nunique(),
            'Importe Primeros Pedidos': x[x['tipo_pedido'] == 'Primer Pedido']['importe_pedido'].sum(),
            'Importe Recurrentes': x[x['tipo_pedido'] == 'Recurrente']['importe_pedido'].sum(),
            'Tiempo Medio Recurrencia (Días)': x['dias_desde_anterior'].mean()
        }))
        resumen['% Recurrentes'] = (resumen['Clientes Recurrentes'] / resumen['Clientes Adquiridos'] * 100)
        resumen = resumen.fillna(0).round(2)
        return resumen[['Clientes Adquiridos', '% Recurrentes', 'Importe Primeros Pedidos', 'Importe Recurrentes', 'Tiempo Medio Recurrencia (Días)']]

    tabla_anyo_mes = crear_tabla_kpis(df_pedidos, 'cohorte_adquisicion')
    tabla_estado = crear_tabla_kpis(df_pedidos, 'state').sort_values('Clientes Adquiridos', ascending=False)
    
    return tabla_anyo_mes, tabla_estado

# Ejecutamos la función (Streamlit mostrará un loader de forma automática si tarda)
tabla_anyo_mes, tabla_estado = cargar_y_preparar_datos('dataset.json') # Asegúrate del nombre correcto

st.divider()

st.subheader("🗓️ Análisis por Cohorte Año-Mes")

fig_temporal, ax = plt.subplots(1, 2, figsize=(16, 6))

tabla_anyo_mes[['Importe Primeros Pedidos', 'Importe Recurrentes']].plot(
    kind='bar', stacked=True, ax=ax[0], color=['dodgerblue', 'orangered']
)
ax[0].set_title('Evolución de Ingresos por Año-Mes', fontsize=14)
ax[0].set_ylabel('Importe ($)')
ax[0].set_xlabel('Año-Mes de Adquisición')
ax[0].tick_params(axis='x', rotation=45)

ax[1].plot(
    tabla_anyo_mes.index, tabla_anyo_mes['% Recurrentes'], 
    marker='o', color='#2ca02c', linewidth=2
)
ax[1].set_title('% de Clientes Recurrentes por Año-Mes', fontsize=14)
ax[1].set_ylabel('% Recurrencia')
ax[1].set_xlabel('Año-Mes de Adquisición')
ax[1].tick_params(axis='x', rotation=45)
if max(tabla_anyo_mes['% Recurrentes']) > 0:
    ax[1].set_ylim(0, max(tabla_anyo_mes['% Recurrentes']) * 1.2)

plt.tight_layout()

# Renderizamos el gráfico en Streamlit
st.pyplot(fig_temporal)

st.markdown("##### Tabla por Año-Mes")

st.dataframe(tabla_anyo_mes, use_container_width=True)

st.divider()

st.subheader("Análisis por estado")

df_mapa = tabla_estado.reset_index()
df_mapa['Ingresos Totales'] = df_mapa['Importe Primeros Pedidos'] + df_mapa['Importe Recurrentes']

fig_mapa = px.choropleth(
    df_mapa,
    locations='state',
    locationmode='USA-states',
    color='Ingresos Totales',
    scope='usa',
    color_continuous_scale='Blues',
    hover_name='state',
    hover_data={
        'state': False,
        'Ingresos Totales': ':$,.2f',
        'Clientes Adquiridos': True,
        '% Recurrentes': ':.2f',
        'Importe Primeros Pedidos': ':$,.2f',
        'Importe Recurrentes': ':$,.2f'
    }
)
fig_mapa.update_layout(geo=dict(bgcolor='rgba(0,0,0,0)'), margin={"r":0,"t":0,"l":0,"b":0})

st.plotly_chart(fig_mapa, use_container_width=True)
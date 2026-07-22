import streamlit as st
import pandas as pd
import json
import numpy as np
import matplotlib.pyplot as plt
import plotly.express as px
import zipfile

st.set_page_config(page_title="Cuadro de Mandos - Ventas", layout="wide")

st.title("📊 Dashboard")
st.markdown("Análisis de recurrencia, ingresos por año-mes y distribución geográfica.")

@st.cache_data
def cargar_y_preparar_datos(ruta_archivo):
    datos_crudos = []
    with zipfile.ZipFile(ruta_archivo, 'r') as z:
        with z.open('dataset.json') as f:
            for linea in f:
                datos_crudos.append(json.loads(linea.decode('utf-8')))
            
    df = pd.json_normalize(datos_crudos, record_path='order_items', 
                           meta=['order_id', 'order_date', 'first_name', 'last_name', 
                                 'gender', 'email', 'phone', 'state', 'zip'])
    
    # convertir las columnas de texto a numéricas
    df['price'] = pd.to_numeric(df['price'])
    df['qty_ordered'] = pd.to_numeric(df['qty_ordered'])
    df['discount_amount'] = pd.to_numeric(df['discount_amount'])

    # convertir la columna de fecha a tipo datetime (formato Día-Mes-Año)
    df['order_date'] = pd.to_datetime(df['order_date'], format='%d-%m-%Y')

    # columna de ventas totales por línea
    df['total'] = (df['price'] * df['qty_ordered']) - df['discount_amount']
    
    # rellenamos con ceros a la izquierda hasta tener 5 dígitos
    df['zip'] = df['zip'].astype(str).str.zfill(5)

    # columnas que identifican unívocamente una línea "única"
    columnas_identificadoras = [
        'order_id', 'order_date', 'first_name', 'last_name',
        'gender', 'email', 'phone', 'state', 'zip',
        'sku', 'product_category', 'price'
    ]

    # agrupamos por esas columnas y sumamos las cantidades y totales
    df = df.groupby(columnas_identificadoras, as_index=False).agg({
        'qty_ordered': 'sum',
        'discount_amount': 'sum',
        'total': 'sum'
    })
    
    # agrupar a nivel de pedido
    # Sumamos el totalpara saber el importe total de cada pedido
    df_pedidos = df.groupby(
        ['order_id', 'order_date', 'email', 'state'], as_index=False
    )['total'].sum().rename(columns={'total': 'importe_pedido'})

    # ordenar cronológicamente por cliente y fecha
    df_pedidos = df_pedidos.sort_values(['email', 'order_date'])

    # número de pedido de cada cliente (1 = el primero, 2 = el segundo...)
    df_pedidos['num_pedido'] = df_pedidos.groupby('email').cumcount() + 1

    # etiquetar si es "Primer Pedido" o "Recurrente"
    df_pedidos['tipo_pedido'] = np.where(
        df_pedidos['num_pedido'] == 1, 'Primer Pedido', 'Recurrente'
    )

    # año y mes de adquisición
    # buscamos la fecha del primer pedido de cada cliente
    df_pedidos['fecha_primera_compra'] = df_pedidos.groupby('email')['order_date'].transform('min')
    # extraemos el Año-Mes
    df_pedidos['anyo_mes_adquisicion'] = df_pedidos['fecha_primera_compra'].dt.to_period('M')

    # tiempo entre recurrencias
    df_pedidos['dias_desde_anterior'] = df_pedidos.groupby('email')['order_date'].diff().dt.days
    
    # función para generar la tabla resumen de KPIs
    def crear_tabla_kpis(df, dimension):
        # agrupamos por la dimensión y calculamos métricas
        resumen = df.groupby(dimension).apply(lambda x: pd.Series({
            'Clientes Adquiridos': x['email'].nunique(),
            'Clientes Recurrentes': x[x['tipo_pedido'] == 'Recurrente']['email'].nunique(),
            'Importe Primeros Pedidos': x[x['tipo_pedido'] == 'Primer Pedido']['importe_pedido'].sum(),
            'Importe Recurrentes': x[x['tipo_pedido'] == 'Recurrente']['importe_pedido'].sum(),
            'Tiempo Medio Recurrencia (Días)': x['dias_desde_anterior'].mean()
        }))

        # calcular el % de recurrencia y formatear
        resumen['% Recurrentes'] = (resumen['Clientes Recurrentes'] / resumen['Clientes Adquiridos'] * 100)

        # limpiar posibles valores nulos (ej. intervalos sin recurrentes)
        resumen = resumen.fillna(0).round(2)

        # reordenar columnas para mejor lectura
        return resumen[[
            'Clientes Adquiridos', '% Recurrentes',
            'Importe Primeros Pedidos', 'Importe Recurrentes',
            'Tiempo Medio Recurrencia (Días)'
        ]]

    tabla_anyo_mes = crear_tabla_kpis(df_pedidos, 'anyo_mes_str')
    tabla_estado = crear_tabla_kpis(df_pedidos, 'state').sort_values('Clientes Adquiridos', ascending=False)
    
    return tabla_anyo_mes, tabla_estado

tabla_anyo_mes, tabla_estado = cargar_y_preparar_datos('dataset.json')

st.divider()

st.subheader("🗓️ Análisis por Año-Mes")

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
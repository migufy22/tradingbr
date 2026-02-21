# app.py - INTERFAZ GRÁFICA STREAMLIT (Separada de la lógica)
"""
Interfaz gráfica del bot de trading.
La lógica corre en un hilo separado para mantener la UI fluida.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import time
import re

# Importar lógica del bot
from bot_logic import (
    get_bot, load_config, save_config, get_default_config,
    now_utc, format_datetime_utc, calcular_tamano_posicion,
    test_binance_connection, test_telegram_connection, get_binance_balance,
    fmt_precio
)

# ============================================
# CONFIGURACIÓN DE PÁGINA
# ============================================
st.set_page_config(
    layout="wide", 
    page_title="TradingBro 1.0",
    page_icon="₿"
)

# ============================================
# CSS PERSONALIZADO
# ============================================
st.markdown("""
<style>
    .block-container {
        padding-left: 1rem !important;
        padding-right: 1rem !important;
        max-width: 100% !important;
    }
    .element-container {
        margin-bottom: 0.5rem !important;
    }
    .stDataFrame {
        font-size: 0.85rem;
    }
    .bot-status-running {
        background-color: #d4edda;
        border: 2px solid #28a745;
        border-radius: 10px;
        padding: 10px;
        text-align: center;
    }
    .bot-status-stopped {
        background-color: #f8d7da;
        border: 2px solid #dc3545;
        border-radius: 10px;
        padding: 10px;
        text-align: center;
    }
    .bot-status-paused {
        background-color: #fff3cd;
        border: 2px solid #ffc107;
        border-radius: 10px;
        padding: 10px;
        text-align: center;
    }
    .log-info { color: #0066cc; }
    .log-success { color: #28a745; }
    .log-warning { color: #ffc107; }
    .log-error { color: #dc3545; }
</style>
""", unsafe_allow_html=True)

# ============================================
# FUNCIONES DE UTILIDAD UI
# ============================================

def formatear_precio(precio):
    if precio >= 1000:
        return f"${precio:,.2f}"
    elif precio >= 1:
        return f"${precio:.4f}"
    else:
        return f"${precio:.8f}".rstrip('0').rstrip('.')

def formatear_fecha_hora(dt):
    """Formatea fecha/hora en formato corto con mes/día hora:minuto UTC+1"""
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt)
        except:
            return dt
    if isinstance(dt, datetime):
        from datetime import timezone, timedelta
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        dt_utc1 = dt.astimezone(timezone(timedelta(hours=1)))
        return dt_utc1.strftime("%m/%d %H:%M")  # MM/DD HH:MM UTC+1
    return str(dt)

def mostrar_estado_bot(bot):
    """Muestra el estado actual del bot con estilo"""
    estado = bot.get_estado()
    if estado['running']:
        if estado['paused']:
            st.markdown('<div class="bot-status-paused"><h3>⏸️ BOT PAUSADO</h3></div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="bot-status-running"><h3>🟢 BOT ACTIVO</h3></div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="bot-status-stopped"><h3>🔴 BOT DETENIDO</h3></div>', unsafe_allow_html=True)

# OPTIMIZACIÓN: Cache del gráfico
@st.cache_data(ttl=600)
def generar_grafico_fibonacci(_market):
    """Genera gráfico de Fibonacci para BTC"""
    df_btc = _market.get_klines_data('BTCUSDC', '4h', 100)
    if df_btc.empty:
        return None
    p0, p1 = df_btc['high'].max(), df_btc['low'].min()
    rango = p0 - p1
    fib_levels = [
        {'level': -0.272, 'label': '1.272', 'color': 'purple', 'dash': 'solid', 'width': 2},
        {'level': 0.0, 'label': '0', 'color': 'black', 'dash': 'solid', 'width': 2},
        {'level': 0.236, 'label': '0.236', 'color': 'gray', 'dash': 'dash', 'width': 1},
        {'level': 0.382, 'label': '0.382 VENTA', 'color': 'green', 'dash': 'solid', 'width': 3},
        {'level': 0.5, 'label': '0.5', 'color': 'gray', 'dash': 'solid', 'width': 1},
        {'level': 0.618, 'label': '0.618 COMPRA', 'color': 'blue', 'dash': 'solid', 'width': 3},
        {'level': 0.786, 'label': '0.786', 'color': 'gray', 'dash': 'dash', 'width': 1},
        {'level': 1.0, 'label': '1', 'color': 'black', 'dash': 'solid', 'width': 2}
    ]
    fig = go.Figure()
    fig.add_trace(go.Candlestick(x=df_btc['timestamp'], open=df_btc['open'], high=df_btc['high'],
                                  low=df_btc['low'], close=df_btc['close'], name='BTC/USDC',
                                  increasing_line_color='#26a69a', increasing_fillcolor='rgba(38, 166, 154, 0.5)',
                                  decreasing_line_color='#ef5350', decreasing_fillcolor='rgba(239, 83, 80, 0.5)'))
    for lvl in fib_levels:
        price = p1 + (rango * (1 - lvl['level']))
        fig.add_hline(y=price, line_color=lvl['color'], line_dash=lvl['dash'], line_width=lvl['width'], opacity=0.7)
        fig.add_annotation(x=-0.01, y=price, text=f"<b>{lvl['label']}</b>", showarrow=False,
                          font=dict(color=lvl['color'], size=22), xanchor='right', yanchor='middle', xref='paper', yref='y')
    fig.update_layout(template='plotly_white', xaxis_rangeslider_visible=False,
                     xaxis=dict(showgrid=False, zeroline=False, showline=True, linewidth=2, linecolor='black',
                               tickfont=dict(size=14)),
                     yaxis=dict(showgrid=True, gridcolor='rgba(0,0,0,0.1)', side='right', showline=True, linewidth=2, linecolor='black',
                               tickfont=dict(size=14)),
                     margin=dict(l=140, r=70, t=10, b=10), height=420, paper_bgcolor='white', plot_bgcolor='white',
                     title=None, showlegend=False)
    return fig


def generar_barra_niveles(trade_data, config, altura=400):
    """Genera barra visual con niveles Fibonacci CONFIGURADOS.
    Altura ajustable para separar/juntar niveles."""
    import plotly.graph_objects as go
    
    orig = trade_data.get('valores_originales', {})
    analysis = trade_data.get('analysis', {})
    
    p1 = orig.get('p1', 0) or analysis.get('punto_1', {}).get('price', 0)
    p0 = orig.get('p0', 0) or analysis.get('punto_0', {}).get('price', 0)
    entrada = trade_data.get('precio_entrada_real', 0) or orig.get('entrada', 0) or analysis.get('precio_entrada', 0)
    tp = orig.get('tp', 0) or analysis.get('precio_tp', 0)
    sl_trigger = orig.get('sl_trigger', 0) or analysis.get('precio_sl_trigger', 0)
    sl_definitivo = orig.get('sl_definitivo', 0) or analysis.get('precio_sl_definitivo', 0)
    precio_actual = analysis.get('precio_actual', 0)
    
    # Niveles Fibonacci CONFIGURADOS (los que el usuario eligió)
    fib_entrada = orig.get('entry_fib', analysis.get('entry_level_usado', config.get('entry_fib_level', 0.618)))
    fib_tp = orig.get('tp_fib', analysis.get('tp_level_usado', config.get('tp_fib_level', 0.382)))
    fib_sl_trigger = orig.get('sl_trigger_fib', config.get('sl_trigger_fib', 0.886))
    fib_sl_rebote = orig.get('sl_rebote_fib', config.get('sl_rebote_fib', 0.786))
    fib_sl_definitivo = orig.get('sl_definitivo_fib', config.get('sl_definitivo_fib', 0.95))
    
    # Si la posición tiene escalón activo, usar niveles de SL del escalón
    sl_escalon_info = trade_data.get('sl_escalon_info')
    if sl_escalon_info and sl_escalon_info.get('proteccion_activa'):
        sl_trigger = sl_escalon_info.get('sl_trigger_precio', sl_trigger)
        sl_definitivo = sl_escalon_info.get('sl_definitivo_precio', sl_definitivo)
        fib_sl_trigger = sl_escalon_info.get('sl_trigger_nivel', fib_sl_trigger)
        fib_sl_rebote = sl_escalon_info.get('sl_rebote_nivel', fib_sl_rebote)
        fib_sl_definitivo = sl_escalon_info.get('sl_definitivo_nivel', fib_sl_definitivo)
    
    if p0 <= p1 or p0 == 0 or p1 == 0:
        return None
    
    rango = p0 - p1
    sl_rebote = p1 + rango * (1 - fib_sl_rebote)
    # Si escalón activo, usar precio directo del escalón para rebote
    if sl_escalon_info and sl_escalon_info.get('proteccion_activa'):
        sl_rebote = sl_escalon_info.get('sl_rebote_precio', sl_rebote)
    
    margen = rango * 0.12
    y_min = p1 - margen
    y_max = p0 + margen
    
    fig = go.Figure()
    
    # Escalones Fib de fondo (gris suave) con equivalencia escalón
    escalones = [1.0, 0.886, 0.786, 0.618, 0.5, 0.382, 0.236, 0.0, -0.272]
    esc_labels = ["+0", "+1", "+2", "+3", "+4", "+5", "+6", "+7", "+8"]
    for fib, lbl in zip(escalones, esc_labels):
        precio_nivel = p1 + rango * (1 - fib)
        if y_min <= precio_nivel <= y_max:
            fig.add_shape(type="line", x0=0.65, x1=0.95, y0=precio_nivel, y1=precio_nivel,
                          line=dict(color='rgba(180,180,180,0.3)', width=1, dash='dot'), xref="paper")
            fig.add_annotation(x=0.92, y=precio_nivel, text=f"<b>{lbl}</b>",
                              showarrow=False, font=dict(color='#aaa', size=18),
                              xanchor='right', yanchor='middle', xref='paper', yref='y')
    
    # Niveles principales con Fib CONFIGURADO visible
    # Colores daltonismo-friendly
    niveles = [
        ("P0",  p0,            0.0,               '#000000', 'solid', 3),
        ("P1",  p1,            1.0,               '#000000', 'solid', 3),
        ("TP",  tp,            fib_tp,            '#0072B2', 'solid', 2.5),
        ("ENT", entrada,       fib_entrada,       '#0072B2', 'dash', 3),
        ("Trigger", sl_trigger,    fib_sl_trigger,    '#E69F00', 'dash', 2),
        ("Rebote", sl_rebote,     fib_sl_rebote,     '#E69F00', 'dot', 1.5),
        ("S.L.", sl_definitivo, fib_sl_definitivo, '#D55E00', 'solid', 3),
    ]
    
    max_perdida_pct = config.get('max_perdida_emergencia_pct', -15.0)
    if entrada > 0:
        precio_emerg = entrada * (1 + max_perdida_pct / 100)
        fib_emerg = 1 - ((precio_emerg - p1) / rango) if rango > 0 else 0
        niveles.append(("🚨", precio_emerg, fib_emerg, '#882255', 'dashdot', 2))
    
    for label, precio, fib_val, color, dash, width in niveles:
        if precio <= 0 or not (y_min <= precio <= y_max):
            continue
        fig.add_shape(type="line", x0=0.65, x1=0.95, y0=precio, y1=precio,
                      line=dict(color=color, width=width, dash=dash), xref="paper")
    
    # Etiquetas con anti-solapamiento: si dos niveles están muy juntos, desplazar verticalmente
    niveles_visibles = [(l, p, f, c) for l, p, f, c, _, _ in niveles if p > 0 and y_min <= p <= y_max]
    niveles_visibles.sort(key=lambda x: x[1])  # Ordenar por precio
    
    umbral_solape = rango * 0.035  # Distancia mínima entre etiquetas (~3.5% del rango)
    
    for i, (label, precio, fib_val, color) in enumerate(niveles_visibles):
        # Determinar yanchor: si hay otro nivel muy cerca arriba, poner esta abajo (y viceversa)
        yanchor = 'middle'
        for j, (_, otro_precio, _, _) in enumerate(niveles_visibles):
            if i == j:
                continue
            distancia = abs(precio - otro_precio)
            if distancia < umbral_solape:
                if precio < otro_precio:
                    yanchor = 'top'     # Este está abajo → etiqueta hacia abajo
                else:
                    yanchor = 'bottom'  # Este está arriba → etiqueta hacia arriba
                break
        
        fig.add_annotation(x=0.6, y=precio,
                          text=f"<b>{label} {fib_val:.3f}</b>",
                          showarrow=False, font=dict(color=color, size=30),
                          xanchor='right', yanchor=yanchor, xref='paper', yref='y')
    
    # Punto del precio actual: círculo magenta con borde negro
    if precio_actual > 0 and y_min <= precio_actual <= y_max:
        pct = ((precio_actual - entrada) / entrada * 100) if entrada > 0 else 0
        signo = '+' if pct >= 0 else ''
        fib_actual = 1 - ((precio_actual - p1) / rango) if rango > 0 else 0
        fig.add_trace(go.Scatter(
            x=[0.8], y=[precio_actual], mode='markers',
            marker=dict(size=14, color='#CC79A7', symbol='circle',
                       line=dict(width=2, color='#000000')),
            showlegend=False,
            hovertext=f"{precio_actual:.6g} | Fib {fib_actual:.3f} | {signo}{pct:.1f}%",
            hoverinfo='text'
        ))
    
    fig.update_layout(
        template='plotly_white', height=altura,
        margin=dict(l=5, r=5, t=5, b=5),
        paper_bgcolor='white', plot_bgcolor='white',
        xaxis=dict(visible=False, range=[0, 1]),
        yaxis=dict(visible=False, range=[y_min, y_max]),
        showlegend=False
    )
    
    return fig

def main():
    # Obtener instancia del bot (singleton)
    bot = get_bot()
    config = bot.config
    
    # --- AUTO INICIO DEL BOT ---
    if not bot.running:
        bot.start()

    # ============================================
    # SIDEBAR - CONTROLES Y CONFIGURACIÓN
    # ============================================
    with st.sidebar:
        # ============================================
        # BARRA DE NIVELES FIBONACCI (primera posición)
        # ============================================
        with st.expander("📊 Niveles del Trade", expanded=True):
            estado_niv = bot.get_estado()
            posiciones_niv = estado_niv.get('open_positions', {})
            ordenes_niv = estado_niv.get('ordenes_pendientes', {})
            
            trades_disponibles = {}
            for sym, pos in posiciones_niv.items():
                trades_disponibles[f"🟢 {sym}"] = pos
            for sym, ord_data in ordenes_niv.items():
                trades_disponibles[f"🟡 {sym}"] = ord_data
            
            if trades_disponibles:
                # Auto-select from Trades tab if set
                trade_keys = list(trades_disponibles.keys())
                default_idx = 0
                if 'selected_trade_symbol' in st.session_state:
                    target = st.session_state['selected_trade_symbol']
                    if target in trade_keys:
                        default_idx = trade_keys.index(target)
                
                selected_trade = st.selectbox(
                    "Moneda",
                    trade_keys,
                    index=default_idx,
                    label_visibility="collapsed"
                )
                
                # Slider de altura para separar niveles
                altura_barra = st.slider("Altura", 200, 800, 800, 50,
                    help="Estira la barra para separar mejor los niveles Fibonacci.",
                    label_visibility="collapsed"
                )
                
                trade_data = trades_disponibles[selected_trade]
                fig_niveles = generar_barra_niveles(trade_data, config, altura=altura_barra)
                if fig_niveles:
                    st.plotly_chart(fig_niveles, use_container_width=True)
                
                # Mostrar info de escalón activo
                sl_esc = trade_data.get('sl_escalon_info')
                max_esc = trade_data.get('max_escalon_alcanzado', 0)
                if max_esc > 0:
                    if sl_esc and sl_esc.get('proteccion_activa'):
                        sl_p = sl_esc.get('sl_trigger_precio', 0)
                        st.caption(f"📈 Escalón máx: **+{max_esc}** | 🛡️ SL protección: **{sl_p:.6g}**")
                    else:
                        st.caption(f"📈 Escalón máx: **+{max_esc}** | ⏳ SL aún no activado")
            else:
                st.caption("Sin trades activos")
        
        st.markdown("---")
        
        # ============================================
        # CONTROL DEL BOT
        # ============================================
        st.header("🤖 Control del Bot")
        
        # Contador de Uptime (usando hora local para consistencia)
        start_time = bot.get_estado().get('start_time')
        if start_time and bot.running:
            uptime = datetime.now() - start_time
            days = uptime.days
            hours, remainder = divmod(uptime.seconds, 3600)
            minutes, _ = divmod(remainder, 60)
            st.markdown(f"⏱️ **Activo:** {days}d {hours}h {minutes}m")
        
        # Estado actual
        mostrar_estado_bot(bot)
        
        st.markdown("---")
        
        # ============================================
        # BOTONES DE CONTROL PRINCIPALES
        # ============================================
        col1, col2 = st.columns(2)
        
        with col1:
            if not bot.running:
                if st.button("▶️ ENCENDER", type="primary", use_container_width=True, help="Inicia el cerebro del bot y empieza a buscar operaciones."):
                    bot.start()
                    st.rerun()
            else:
                if st.button("🛑 APAGAR", type="secondary", use_container_width=True, help="Detiene el bot por completo. No se abrirán nuevas órdenes, pero las abiertas se mantienen."):
                    bot.stop()
                    st.rerun()
        
        with col2:
            if bot.running:
                if bot.paused:
                    if st.button("▶️ REANUDAR", use_container_width=True, help="Reanuda el bot si estaba pausado."):
                        bot.resume()
                        st.rerun()
                else:
                    if st.button("⏸️ PAUSAR", use_container_width=True, help="Pausa temporalmente el bot. No analiza mercado ni compra, pero vigila lo que ya tienes."):
                        bot.pause()
                        st.rerun()
        
        # Botón de test
        if st.button("🧪 TEST CONEXIONES", use_container_width=True, help="Verifica si tus claves API de Binance y Telegram son correctas."):
            with st.spinner("Testeando conexiones..."):
                resultados = bot.test_conexiones()
                for nombre, resultado in resultados.items():
                    if resultado['success']:
                        st.success(f"{nombre.upper()}: {resultado['message']}")
                    else:
                        st.error(f"{nombre.upper()}: {resultado['message']}")
        
        # Sincronización manual con Binance
        if not config.get('modo_demo', True):
            if st.button("🔄 SYNC BINANCE", use_container_width=True, help="Consulta Binance y sincroniza: adopta tokens huérfanos, cancela órdenes fantasma, coloca OCO en compras sin proteger."):
                with st.spinner("Sincronizando con Binance..."):
                    bot._sincronizar_con_binance(config)
                    st.success("✅ Sincronización completada. Revisa los logs.")
                    st.rerun()
        
        st.markdown("---")
        
        # ============================================
        # INFORMACIÓN DE ESTADO
        # ============================================
        estado = bot.get_estado()
        
        st.markdown("### 📊 Estado Actual")
        col_info1, col_info2 = st.columns(2)
        with col_info1:
            st.metric("Posiciones", len(estado['open_positions']))
            st.caption("Número de operaciones abiertas actualmente.")
        with col_info2:
            st.metric("Órdenes", len(estado['ordenes_pendientes']))
            st.caption("Número de órdenes de compra esperando ser ejecutadas.")
        
        if estado['last_update']:
            tiempo_desde = (now_utc() - estado['last_update']).total_seconds()
            # Color según frescura: verde <60s, amarillo <180s, rojo >180s
            color_update = '🟢' if tiempo_desde < 60 else ('🟡' if tiempo_desde < 180 else '🔴')
            st.caption(f"{color_update} Último escaneo: {int(tiempo_desde)}s")
            st.caption("Tiempo desde que el bot terminó su último ciclo de análisis.")
        
        if estado['btc_status']:
            nivel = estado['btc_status'].get('nivel_alerta', 'NORMAL')
            color = {'NORMAL': '🟢', 'MODERADA': '🟡', 'FUERTE': '🟠', 'SEVERA': '🔴'}.get(nivel, '⚪')
            st.info(f"{color} BTC: {nivel}")
            st.caption("Estado de Bitcoin. Si cae mucho, el bot se protegerá.")
        
        st.info(f"🌊 Fase: {estado['fase_mercado']}")
        st.caption("¿Está el mercado en general subiendo, bajando o lateral?")
        
        st.markdown("---")

        # ============================================
        # 1. BÚSQUEDA DE MONEDAS
        # ============================================
        with st.expander("1️⃣ Búsqueda de Monedas", expanded=False):
            st.caption("Qué monedas analizar, en qué temporalidades, y cómo priorizarlas.")
            
            # Configuración general
            col_conf1, col_conf2 = st.columns(2)
            with col_conf1:
                config['num_monedas_analizar'] = st.slider(
                    "Monedas a analizar", 10, 100, 
                    config.get('num_monedas_analizar', 50), 10,
                    help="¿Cuántas de las mejores monedas (por volumen) analizamos? Más monedas = más oportunidades pero más lento."
                )
            with col_conf2:
                config['min_beneficio_pct'] = st.slider(
                    "Beneficio Mínimo (%)", 0.0, 5.0, 
                    config.get('min_beneficio_pct', 0.5), 0.1,
                    help="¿Cuánto dinero quiero ganar mínimo en cada operación? Si el cálculo da menos de esto, el bot ignora la señal."
                )
                config['min_risk_reward'] = st.slider(
                    "Risk:Reward Mínimo", 0.5, 3.0,
                    config.get('min_risk_reward', 1.0), 0.1,
                    help="Ratio mínimo entre ganancia potencial y pérdida. 1.0 = no arriesgar más de lo que puedo ganar. 1.5 = quiero ganar 1.5x lo que arriesgo."
                )
            
            # Filtros de calidad
            # Monedas excluidas
            monedas_excluidas_text = st.text_input(
                "🚫 Monedas excluidas (separadas por coma)",
                value=", ".join(config.get('monedas_excluidas', [])),
                help="Monedas que NO quieres analizar. Ejemplo: BTCUSDC, ETHUSDC, XRPUSDC"
            )
            if monedas_excluidas_text.strip():
                config['monedas_excluidas'] = [m.strip().upper() for m in monedas_excluidas_text.split(',') if m.strip()]
            else:
                config['monedas_excluidas'] = []
            
            # Monedas en HOLD (no tocar)
            hold_coins_text = st.text_input(
                "🔒 Monedas en HOLD (separadas por coma)",
                value=", ".join(config.get('hold_coins', [])),
                help="Monedas que tienes en Binance pero NO quieres que el bot toque. Pon el SÍMBOLO sin USDC. Ejemplo: BTC, ETH, SOL"
            )
            if hold_coins_text.strip():
                config['hold_coins'] = [m.strip().upper() for m in hold_coins_text.split(',') if m.strip()]
            else:
                config['hold_coins'] = []
            
            col_vol1, col_vol2 = st.columns(2)
            with col_vol1:
                # Opciones de volumen predefinidas (en miles)
                vol_opciones = {
                    0: "Sin filtro",
                    50000: "50K USDC",
                    100000: "100K USDC",
                    250000: "250K USDC",
                    500000: "500K USDC",
                    1000000: "1M USDC",
                    5000000: "5M USDC"
                }
                vol_actual = config.get('min_volumen_24h', 100000)
                # Encontrar el valor más cercano en opciones
                vol_key = min(vol_opciones.keys(), key=lambda x: abs(x - vol_actual))
                config['min_volumen_24h'] = st.select_slider(
                    "Volumen mínimo 24h",
                    options=list(vol_opciones.keys()),
                    value=vol_key,
                    format_func=lambda x: vol_opciones[x],
                    help="Solo analiza monedas con este volumen mínimo de trading en las últimas 24h. Más volumen = más liquidez y menos riesgo de manipulación."
                )

            st.markdown("---")
            st.caption("📊 <b>Nivel de Calidad Mínimo (Score)</b><br>El bot puntúa cada oportunidad del 0 al 100. Aquí decides qué nota mínima debe sacar para comprar.", unsafe_allow_html=True)
            
            # Configuración por temporalidad
            c1, c2, c3 = st.columns(3)
            
            with c1:
                st.markdown("⏰ **1H**")
                val_1h = st.slider("Score Min", 0, 100, config.get('min_score_1h', 50), key="slider_1h", help="Exigencia para operaciones a corto plazo (1 hora). Si lo subes, solo comprarás señales muy seguras.")
                config['min_score_1h'] = val_1h
            
            with c2:
                st.markdown("⏰ **4H**")
                val_4h = st.slider("Score Min", 0, 100, config.get('min_score_4h', 50), key="slider_4h", help="Exigencia para operaciones a medio plazo (4 horas).")
                config['min_score_4h'] = val_4h
            
            with c3:
                st.markdown("⏰ **24H**")
                val_24h = st.slider("Score Min", 0, 100, config.get('min_score_1d', 50), key="slider_24h", help="Exigencia para operaciones de un día.")
                config['min_score_1d'] = val_24h

            st.markdown("---")
            
            config['estrategia_scoring'] = st.radio(
                "Estrategia de Puntuación",
                ["A", "B", "C"],
                index=["A", "B", "C"].index(config.get('estrategia_scoring', 'C')),
                horizontal=True,
                help="A: Prioriza monedas cercanas al punto de entrada. B: Prioriza monedas con mayor momentum (subiendo fuerte). C: Equilibrado entre precio, momentum y volumen."
            )
            
            criterio_opciones = {"score": "📊 Por Puntuación", "subida": "📈 Por Mayor Subida 24h"}
            criterio_actual = config.get('criterio_ordenamiento', 'score')
            config['criterio_ordenamiento'] = st.radio(
                "Ordenar Oportunidades por:",
                options=list(criterio_opciones.keys()),
                format_func=lambda x: criterio_opciones[x],
                index=list(criterio_opciones.keys()).index(criterio_actual),
                horizontal=True,
                help="📊 Por Puntuación: Ordena según la nota que el bot le da a cada oportunidad. 📈 Por Mayor Subida: Ordena por las monedas que más han subido en las últimas 24 horas."
            )

            if st.button("💾 Guardar Búsqueda", help="Aplica estos filtros para el siguiente escaneo del mercado."):
                save_config(config)
                bot.reload_config()
                st.success("✅ Filtros guardados")
        
        st.markdown("---") 

        # ============================================
        # 2. CAPITAL Y POSICIONES
        # ============================================
        with st.expander("2️⃣ Capital y Modo", expanded=False):
            st.caption("Cuánto invertir, modo demo/real, y número de posiciones simultáneas.")
            
            # --- SELECCIÓN DE MONEDA ---
            opciones_monedas = ["USDC", "BUSD", "EUR"] 
            moneda_seleccionada = st.selectbox(
                "Moneda de Compra (Quote Asset)", 
                opciones_monedas, 
                index=0,
                help="¿En qué moneda quieres tener tus beneficios? (USDC es el dólar digital estable)."
            )
            config['pares_trading'] = [moneda_seleccionada]

            st.markdown("---")

            # --- MODO DEMO VS REAL ---
            config['modo_demo'] = st.checkbox(
                "🎮 Modo Demo (Sin dinero real)", 
                config.get('modo_demo', True),
                help="⚠️ ACTÍVALO SIEMPRE AL PRINCIPIO. Usa dinero falso para probar el bot sin riesgo. Desactívalo solo cuando estés listo para usar dinero real."
            )
            
            # Avisar si protección forzó DEMO
            if config.get('modo_demo', True) and bot.modo_proteccion_activado:
                st.warning("⚠️ Modo Demo activado por **protección de pérdidas**. Desmarca la casilla y guarda para volver a REAL.")

            if config['modo_demo']:
                st.markdown("### 🕹️ Configuración Demo")
                config['balance_disponible'] = st.number_input(
                    "Saldo Virtual Disponible", 
                    min_value=0.0, 
                    value=float(config.get('balance_disponible', 10000.0)), 
                    step=100.0,
                    help="Cantidad de dinero falso que simulas tener para practicar."
                )
            else:
                st.markdown("### 🔗 Configuración Real (Binance)")
                col_bal1, col_bal2 = st.columns([3, 1])
                with col_bal2:
                    if st.button("🔄 Actualizar Saldo", help="Conecta con Binance para ver cuánto dinero real tienes ahora mismo."):
                        with st.spinner("Conectando con Binance..."):
                            saldo_real = get_binance_balance(config.get('binance_api_key'), config.get('binance_api_secret'), moneda_seleccionada)
                            if saldo_real > 0:
                                config['balance_disponible'] = saldo_real
                                st.success(f"Saldo actualizado: {saldo_real:.2f} {moneda_seleccionada}")
                            else:
                                st.error("No se pudo obtener el saldo. Revisa APIs.")
                
                with col_bal1:
                    st.info(f"Saldo a usar: **{config['balance_disponible']:.2f} {moneda_seleccionada}**")

            st.markdown("---")

            # --- GESTIÓN DE ÓRDENES Y TAMAÑO ---
            col_l1, col_l2 = st.columns(2)
            with col_l1:
                config['max_positions'] = st.slider(
                    "Máx. Órdenes Simultáneas", 1, 20, 
                    config.get('max_positions', 5),
                    help="¿Cuántas operaciones diferentes quieres tener abiertas a la vez? No te pases si no tienes mucho dinero."
                )
            
            with col_l2:
                config['min_score_compra'] = st.slider(
                    "Score Mínimo (Global)", 30, 90, 
                    config.get('min_score_compra', 60),
                    help="Este es un filtro de seguridad adicional. Si una oportunidad es mala, aunque tenga el precio perfecto, no la comprará si su puntuación es menor a esto."
                )

            # Cálculo de cuánto meter en cada operación
            st.markdown("#### 💰 Tamaño por Operación")
            modo_capital_ui = st.radio(
                "¿Cómo calcular el tamaño?", 
                ["Porcentaje (%)", "Importe Fijo ($)"], 
                index=0 if config.get('modo_capital', 'porcentaje') == 'porcentaje' else 1,
                horizontal=True,
                label_visibility="collapsed",
                help="Estrategia de apuestas: ¿Prefieres arriesgar un porcentaje de lo que tienes (Compuesto) o una cantidad fija (Simple)?"
            )
            
            if modo_capital_ui == "Porcentaje (%)":
                config['modo_capital'] = "porcentaje"
                config['capital_porcentaje'] = st.slider(
                    "% del Saldo por Orden", 
                    1, 100, 
                    config.get('capital_porcentaje', 10), 
                    help="Ejemplo: Si tienes 1000 y pones 10%, el bot usará 100$ para la primera operación. Si ganas, el 10% de la nueva cantidad será más dinero."
                )
                ejemplo = (config['balance_disponible'] * config['capital_porcentaje']) / 100
                st.caption(f"👉 Invertirás aprox: **{ejemplo:.2f} {moneda_seleccionada}** por trade.")
            else:
                config['modo_capital'] = "fijo"
                config['capital_fijo'] = st.number_input(
                    "Importe Fijo por Operación", 
                    min_value=10.0, 
                    value=float(config.get('capital_fijo', 100.0)), 
                    step=10.0,
                    help="Siempre usarás esta cantidad exacta para comprar, sin importar si ganas o pierdes antes."
                )
                st.caption(f"👉 Invertirás exactamente: **{config['capital_fijo']:.2f} {moneda_seleccionada}** por trade.")

            if st.button("💾 Guardar Configuración", help="Guarda los cambios de dinero y límites."):
                save_config(config)
                # Si el usuario desactiva modo demo manualmente, resetear protección
                if not config.get('modo_demo', True) and bot.modo_proteccion_activado:
                    bot.modo_proteccion_activado = False
                    bot.log("🔓 Protección reseteada: usuario cambió manualmente a MODO REAL", "INFO")
                bot.reload_config()
                st.success("✅ Configuración guardada")

        # ============================================
        # 3. ESTRATEGIA FIBONACCI
        # ============================================
        with st.expander("3️⃣ Entrada y Salida", expanded=False):
            st.caption("Niveles Fibonacci de compra y venta, ajustes para caídas de BTC, y método de búsqueda de suelos.")
            
            def fib_control(label, key_config, is_buy=True):
                """Control combinado de SelectBox (Base) y Slider (Ajuste Fino)"""
                fib_options = [0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0, 1.272, 1.618]
                current_val = config.get(key_config, 0.618 if is_buy else 0.382)
                
                closest_base = min(fib_options, key=lambda x: abs(x - current_val))
                calculated_offset = current_val - closest_base
                
                if is_buy:
                    # Para compras: slider de 0 a -0.02
                    display_offset = max(-0.02, min(0.0, calculated_offset))
                else:
                    # Para ventas: slider de 0 a 0.02
                    display_offset = max(0.0, min(0.02, calculated_offset))

                base_col, offset_col = st.columns([1, 1])
                
                with base_col:
                    texto_ayuda_base = ""
                    if 'entry' in key_config: texto_ayuda_base = "Nivel ideal de compra (0.618 es el estándar 'de oro')."
                    elif 'tp' in key_config: texto_ayuda_base = "Nivel ideal de venta para asegurar ganancias (0.382 es seguro)."
                    elif 'sl' in key_config: texto_ayuda_base = "Nivel donde activamos la alarma de pérdida."
                    elif 'reentry' in key_config: texto_ayuda_base = "Nivel más agresivo si el precio sigue bajando."

                    new_base = st.selectbox(
                        f"{label} (Nivel Base)",
                        options=fib_options,
                        index=fib_options.index(closest_base),
                        format_func=lambda x: f"{x:.3f}",
                        key=f"base_{key_config}",
                        help=texto_ayuda_base
                    )
                
                with offset_col:
                    if is_buy:
                        # Para compras: slider de 0 a -0.02
                        offset = st.slider(
                            "Ajuste Fino (0 a -0.02)", 
                            -0.02, 0.0, display_offset, 0.001, format="%.3f",
                            help="Ajusta el nivel. Negativo = compra más bajo.",
                            key=f"offset_{key_config}"
                        )
                    else:
                        # Para ventas: slider de 0 a 0.02
                        offset = st.slider(
                            "Ajuste Fino (0 a 0.02)", 
                            0.0, 0.02, display_offset, 0.001, format="%.3f",
                            help="Ajusta el nivel. Positivo = vende más alto.",
                            key=f"offset_{key_config}"
                        )
                
                final_val = new_base + offset
                st.markdown(f"<small style='color:gray;'>Nivel Final: <b>{final_val:.4f}</b></small>", unsafe_allow_html=True)
                st.markdown("---")
                return final_val

            # --- 1. NIVELES PRINCIPALES ---
            st.markdown("---")
            st.markdown("#### 📐 Niveles de Entrada y Salida")
            st.caption("Dónde comprar y dónde vender.")
            config['entry_fib_level'] = fib_control("Nivel de Entrada", 'entry_fib_level', is_buy=True)
            
            # --- ENTRADA BTC EN CAÍDA ---
            st.markdown("---")
            st.markdown("#### 🔻 Ajuste si BTC Cae")
            st.caption("Cuando Bitcoin cae, el bot puede comprar más abajo (entrada alternativa más segura).")
            col_btc_ent1, col_btc_ent2 = st.columns([1, 1])
            with col_btc_ent1:
                config['entrada_btc_caida_activa'] = st.checkbox(
                    "Activar entrada alternativa si BTC cae o Fase BAJADA",
                    config.get('entrada_btc_caida_activa', False),
                    help="Si BTC tiene Alerta Moderada O la fase del mercado es BAJADA, usa 0.786 como nivel de entrada. Compra más bajo para protegerte."
                )
            with col_btc_ent2:
                if config['entrada_btc_caida_activa']:
                    config['entrada_btc_caida_ajuste'] = st.slider(
                        "Ajuste fino (0 a -0.02)",
                        -0.02, 0.0,
                        config.get('entrada_btc_caida_ajuste', 0.0),
                        0.001,
                        format="%.3f",
                        help="Ajuste sobre el nivel 0.786. Ej: -0.01 = 0.776"
                    )
                    nivel_final_btc = 0.786 + config['entrada_btc_caida_ajuste']
                    st.caption(f"Nivel de entrada si BTC cae: **{nivel_final_btc:.3f}**")
                else:
                    st.info("Desactivado")
            st.markdown("---")
            
            config['tp_fib_level'] = fib_control("Take Profit (TP 1)", 'tp_fib_level', is_buy=False)

            # --- VENTA BTC EN CAÍDA ---
            st.markdown("##### 📈 Venta BTC en Caída")
            col_btc_vta1, col_btc_vta2 = st.columns([1, 1])
            with col_btc_vta1:
                config['venta_btc_caida_activa'] = st.checkbox(
                    "Activar venta alternativa si BTC cae",
                    config.get('venta_btc_caida_activa', False),
                    help="Si BTC tiene Alerta Moderada, usa 0.5 como nivel de venta en lugar del configurado arriba."
                )
            with col_btc_vta2:
                if config['venta_btc_caida_activa']:
                    config['venta_btc_caida_ajuste'] = st.slider(
                        "Ajuste fino (0 a 0.02)",
                        0.0, 0.02,
                        config.get('venta_btc_caida_ajuste', 0.0),
                        0.001,
                        format="%.3f",
                        help="Ajuste sobre el nivel 0.5. Ej: +0.01 = 0.51"
                    )
                    nivel_final_btc_vta = 0.5 + config['venta_btc_caida_ajuste']
                    st.caption(f"Nivel de venta si BTC cae: **{nivel_final_btc_vta:.3f}**")
                else:
                    st.info("Desactivado")
            st.markdown("---")

            # --- 2. REENTRADAS ---
            fase_mercado = estado.get('fase_mercado', 'DESCONOCIDO')
            btc_alerta = estado.get('btc_status', {}).get('nivel_alerta', 'NORMAL')
            reentradas_bloqueadas = (fase_mercado == 'BAJADA' or btc_alerta != 'NORMAL')
            
            if reentradas_bloqueadas:
                st.warning("⚠️ Reentradas bloqueadas por mercado BTC.")
            
            reentradas_activas = st.checkbox(
                "Activar Reentradas", 
                value=config.get('activar_reentrada_solo_subida', False), 
                disabled=reentradas_bloqueadas,
                help="⚠️ PELIGROSO: Si el precio sigue bajando después de comprar, ¿comprar más para bajar el precio medio? Solo para expertos."
            )
            config['activar_reentrada_solo_subida'] = reentradas_activas and not reentradas_bloqueadas

            if reentradas_activas and not reentradas_bloqueadas:
                st.markdown("#### 🔄 Configuración Reentrada")
                config['reentry_fib_level'] = fib_control("Valor Reentrada", 'reentry_fib_level', is_buy=True)
                config['tp2_fib_level'] = fib_control("2ª Venta (TP2)", 'tp2_fib_level', is_buy=False)

            st.markdown("---")

            # --- LOOKBACK P1 ---
            st.markdown("---")
            st.markdown("#### 🔍 Método de Búsqueda del Suelo (P1)")
            st.caption("Cómo identifica el bot el punto mínimo reciente. 'Consenso' combina varios métodos.")
            
            metodo_opciones = {
                "repetido": "🔄 Repetido",
                "inflexion_low": "📉 Inflexión Low",
                "inflexion_close": "📊 Inflexión Close",
                "minimo_absoluto": "📍 Mínimo Absoluto",
                "consenso": "🎯 Consenso",
                "soporte_historico": "🏛️ Soporte Histórico"
            }
            metodo_actual = config.get('metodo_p1', 'repetido')
            if metodo_actual not in metodo_opciones:
                metodo_actual = 'repetido'
            config['metodo_p1'] = st.radio(
                "Método de detección P1:",
                options=list(metodo_opciones.keys()),
                format_func=lambda x: metodo_opciones[x],
                index=list(metodo_opciones.keys()).index(metodo_actual),
                horizontal=True,
                help="🔄 Repetido: Mínimo más frecuente. 📉 Inflexión Low: Mínimo antes de subir. "
                     "📊 Inflexión Close: Cierre antes de subir. 📍 Mínimo Absoluto: Precio más bajo. "
                     "🎯 Consenso: Combina varios. 🏛️ Soporte Histórico: Busca el soporte con MÁS TOQUES de velas en la historia."
            )
            
            col_p1_1, col_p1_2 = st.columns(2)
            with col_p1_1:
                max_lookback = 500 if config.get('metodo_p1') == 'soporte_historico' else 150
                config['lookback_p1'] = st.slider(
                    "Lookback P1 (Velas atrás)", 
                    2, max_lookback, 
                    min(config.get('lookback_p1', 50), max_lookback), 1,
                    help="¿Cuántas velas hacia atrás analizar? Soporte Histórico funciona mejor con 200-500 velas."
                )
            with col_p1_2:
                if config['metodo_p1'] in ['inflexion_low', 'inflexion_close', 'consenso']:
                    config['confirmacion_ascenso_velas'] = st.slider(
                        "Velas confirmación ascenso", 
                        2, 10, 
                        config.get('confirmacion_ascenso_velas', 3), 1,
                        help="¿Cuántas velas alcistas consecutivas confirman que el precio está subiendo?"
                    )
                elif config['metodo_p1'] == 'soporte_historico':
                    config['min_fuerza_soporte_historico'] = st.slider(
                        "Fuerza mínima del soporte",
                        2, 20,
                        config.get('min_fuerza_soporte_historico', 6), 1,
                        help="Mínimo de toques de velas para considerar un nivel como soporte. "
                             "Más alto = solo soportes muy probados. 6-10 es un buen rango."
                    )
                else:
                    st.caption("ℹ️ Solo aplica a métodos Inflexión/Consenso")
            
            # Info del método Soporte Histórico
            if config['metodo_p1'] == 'soporte_historico':
                st.markdown("""
                <div style='background: #1a2e1a; border-radius: 8px; padding: 10px; margin: 8px 0; font-size: 0.82em; color: #eee;'>
                <b>🏛️ Soporte Histórico</b><br/>
                En vez de buscar "¿cuál es el mínimo reciente?", busca "¿dónde ha rebotado más veces el precio?"<br/>
                • Mira mucho más atrás (300-500 velas)<br/>
                • Cuenta toques de velas en cada zona de precio<br/>
                • Elige el soporte con MÁS TOQUES por debajo del precio actual<br/>
                • El P1 puede ser más bajo que el mínimo reciente si hay un suelo histórico fuerte ahí<br/>
                <br/>
                <b>💡 Ejemplo THEUSDC:</b> El mínimo reciente es 0.2581 (spike), pero en 0.2558 hay un soporte donde 
                muchas velas han rebotado → P1 = 0.2558 → rango más amplio → más beneficio.
                </div>
                """, unsafe_allow_html=True)
            
            # Configuración de Consenso
            if config['metodo_p1'] == 'consenso':
                st.markdown("---")
                st.markdown("##### ⚙️ Configuración de Consenso")
                st.caption("Selecciona qué métodos usar y cómo combinarlos para encontrar el mejor suelo.")
                
                col_cons1, col_cons2 = st.columns(2)
                with col_cons1:
                    st.markdown("**Métodos a usar:**")
                    config['consenso_usar_repetido'] = st.checkbox(
                        "🔄 Usar Repetido", 
                        config.get('consenso_usar_repetido', True),
                        help="Incluir método que busca precio mínimo más frecuente."
                    )
                    config['consenso_usar_inflexion_low'] = st.checkbox(
                        "📉 Usar Inflexión Low", 
                        config.get('consenso_usar_inflexion_low', True),
                        help="Incluir método que busca mínimo antes de ascenso."
                    )
                    config['consenso_usar_inflexion_close'] = st.checkbox(
                        "📊 Usar Inflexión Close", 
                        config.get('consenso_usar_inflexion_close', False),
                        help="Incluir método que busca cierre antes de ascenso."
                    )
                    config['consenso_usar_minimo'] = st.checkbox(
                        "📍 Usar Mínimo Absoluto", 
                        config.get('consenso_usar_minimo', True),
                        help="Incluir el precio más bajo del periodo."
                    )
                    config['consenso_usar_soporte_historico'] = st.checkbox(
                        "🏛️ Usar Soporte Histórico", 
                        config.get('consenso_usar_soporte_historico', True),
                        help="Incluir soporte histórico (zonas con muchos toques)."
                    )
                
                with col_cons2:
                    st.markdown("**Estrategia de decisión:**")
                    estrategia_opciones = {
                        "minimo_validado": "✅ Mínimo validado (recomendado)",
                        "mas_bajo": "📉 Siempre el más bajo",
                        "mayoria": "🗳️ Mayoría coincidente"
                    }
                    estrategia_actual = config.get('consenso_estrategia', 'minimo_validado')
                    if estrategia_actual not in estrategia_opciones:
                        estrategia_actual = 'minimo_validado'
                    config['consenso_estrategia'] = st.radio(
                        "Si los métodos no coinciden:",
                        options=list(estrategia_opciones.keys()),
                        format_func=lambda x: estrategia_opciones[x],
                        index=list(estrategia_opciones.keys()).index(estrategia_actual),
                        help="✅ Mínimo validado: Coge el más bajo SOLO si otro método lo confirma. Si nadie lo confirma (mínimo antiguo aislado), usa el grupo con más consenso. 📉 Más bajo: Siempre elige el suelo más profundo. 🗳️ Mayoría: Elige el suelo donde coinciden más métodos."
                    )
                    
                    config['consenso_tolerancia'] = st.slider(
                        "Tolerancia coincidencia (%)",
                        0.1, 2.0,
                        min(2.0, max(0.1, config.get('consenso_tolerancia', 0.02) * 100)),
                        0.1,
                        help="Dos precios se consideran 'iguales' si difieren menos de este porcentaje."
                    ) / 100
                    
                    # Recencia Override
                    st.markdown("---")
                    st.markdown("##### ⏱️ Override por Recencia")
                    config['consenso_override_recencia'] = st.checkbox(
                        "Preferir mínimo reciente sobre mayoría",
                        config.get('consenso_override_recencia', True),
                        help="Si el mínimo absoluto es MÁS RECIENTE y >3% más bajo que el grupo mayoritario, usarlo en su lugar. "
                             "Lógica: si el precio ya rompió la zona de consenso y bajó más, esa zona ya no es soporte válido."
                    )
                    if config['consenso_override_recencia']:
                        config['consenso_override_pct'] = st.slider(
                            "Diferencia mín. para override (%)", 1.0, 10.0,
                            config.get('consenso_override_pct', 3.0), 0.5,
                            help="El mínimo reciente debe ser al menos X% más bajo que la mayoría para activar el override. "
                                 "3% = buen equilibrio. Más bajo = más sensible, más alto = más conservador."
                        )
                
                # Mostrar info de métodos activos
                metodos_activos = []
                if config['consenso_usar_repetido']: metodos_activos.append("Repetido")
                if config['consenso_usar_inflexion_low']: metodos_activos.append("Inflexión Low")
                if config['consenso_usar_inflexion_close']: metodos_activos.append("Inflexión Close")
                if config['consenso_usar_minimo']: metodos_activos.append("Mínimo")
                if config.get('consenso_usar_soporte_historico', True): metodos_activos.append("Soporte Histórico")
                
                if len(metodos_activos) < 2:
                    st.warning("⚠️ Selecciona al menos 2 métodos para que el consenso tenga sentido.")
                else:
                    st.info(f"✅ Usando {len(metodos_activos)} métodos: {', '.join(metodos_activos)}")
            
            if st.button("💾 Guardar Entrada y Salida", help="Guarda niveles Fibonacci, ajustes BTC y método P1."):
                save_config(config)
                bot.reload_config()
                st.success("✅ Configuración de Entrada y Salida guardada")
        
        # ============================================
        # 4. STOP LOSS
        # ============================================
        with st.expander("4️⃣ Stop Loss", expanded=False):
            st.caption("Sistema de 3 niveles: Trigger → Espera rebote → Si no rebota, cierra. Evita vender por un pico momentáneo.")
            
            st.markdown("""
            <div style='background: #1a1a2e; border-radius: 8px; padding: 10px; margin: 8px 0; font-size: 0.82em; color: #eee;'>
            <b>¿Cómo funciona?</b><br/>
            1️⃣ <b>Trigger:</b> El precio baja a este nivel → se activa la alarma<br/>
            2️⃣ <b>Rebote:</b> Si rebota a este nivel → vende con la menor pérdida posible<br/>
            3️⃣ <b>S.L.:</b> Si no rebota en N velas → vende al precio actual (cortar pérdidas)<br/>
            <br/>⚡ Los niveles son Fibonacci sobre el rango P1→P0. Más cerca de 1.0 = más cerca del suelo (P1).
            </div>
            """, unsafe_allow_html=True)
            
            fib_options = [0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 0.886, 1.0]
            
            base_trigger = config.get('sl_trigger_fib', 0.886)
            closest_base_trigger = min(fib_options, key=lambda x: abs(x - base_trigger))
            current_offset_trigger = int((base_trigger - closest_base_trigger) * 1000)
            current_offset_trigger = max(0, min(60, abs(current_offset_trigger)))

            st.markdown("### ⚡ Nivel 1: Trigger")
            col_b1, col_s1 = st.columns([1, 1])
            with col_b1:
                new_base_trigger = st.selectbox("Base Trigger", fib_options, index=fib_options.index(closest_base_trigger), key="sl_base_trig")
            with col_s1:
                adj_trigger = st.slider("Ajuste (0 a -0.06)", 0, 60, current_offset_trigger, help="Resta este valor (ej: 10 = 0.01) al nivel base.")
            config['sl_trigger_fib'] = new_base_trigger - (adj_trigger / 1000.0)
            st.caption(f"Nivel Final: {config['sl_trigger_fib']:.4f}")

            st.markdown("---")

            base_rebote = config.get('sl_rebote_fib', 0.786)
            closest_base_rebote = min(fib_options, key=lambda x: abs(x - base_rebote))
            current_offset_rebote = int((base_rebote - closest_base_rebote) * 1000)
            current_offset_rebote = max(0, min(25, current_offset_rebote))

            st.markdown("### 🏀 Nivel 2: Rebote")
            col_b2, col_s2 = st.columns([1, 1])
            with col_b2:
                new_base_rebote = st.selectbox("Base Rebote", fib_options, index=fib_options.index(closest_base_rebote), key="sl_base_reb")
            with col_s2:
                adj_rebote = st.slider("Ajuste (0 a 0.025)", 0, 25, current_offset_rebote, help="Suma este valor (ej: 10 = 0.01) al nivel base.")
            config['sl_rebote_fib'] = new_base_rebote + (adj_rebote / 1000.0)
            st.caption(f"Nivel Final: {config['sl_rebote_fib']:.4f}")

            st.markdown("---")

            base_def = config.get('sl_definitivo_fib', 0.95)
            closest_base_def = min(fib_options, key=lambda x: abs(x - base_def))
            current_offset_def = int((base_def - closest_base_def) * 1000)
            current_offset_def = max(0, min(60, current_offset_def))

            st.markdown("### 💣 Nivel 3: S.L.")
            col_b3, col_s3 = st.columns([1, 1])
            with col_b3:
                new_base_def = st.selectbox("Base S.L.", fib_options, index=fib_options.index(closest_base_def), key="sl_base_def")
            with col_s3:
                adj_def = st.slider("Ajuste (0 a +0.06)", 0, 60, current_offset_def, help="Suma este valor (ej: 10 = 0.01, 30 = 0.03) al nivel base.")
            config['sl_definitivo_fib'] = new_base_def + (adj_def / 1000.0)
            st.caption(f"Nivel Final: {config['sl_definitivo_fib']:.4f}")
            
            st.markdown("---")
            config['sl_timeout_candles'] = st.slider("⏱️ Velas para Esperar Rebote", 1, 20, config.get('sl_timeout_candles', 5), 1,
                help="Si el precio no rebota en este número de velas después del trigger, vende definitivamente.")
            
            st.markdown("---")
            st.markdown("#### 🚨 SL Emergencia (anti-crash)")
            st.caption("Si el análisis técnico falla (tras un crash), esta protección vende automáticamente.")
            config['max_perdida_emergencia_pct'] = st.slider(
                "Pérdida máxima absoluta (%)", -30.0, -5.0, 
                config.get('max_perdida_emergencia_pct', -15.0), 0.5,
                help="Si la pérdida supera este % y el análisis técnico no funciona, venta forzada inmediata. Protección contra crashes."
            )
            
            if st.button("💾 Guardar Stop Loss"):
                save_config(config)
                bot.reload_config()
                st.success("✅ SL guardado")
        
        # ============================================
        # 5. ESCALONES Y REENTRADAS
        # ============================================
        with st.expander("5️⃣ Escalones y Reentradas", expanded=False):
            st.caption("Protección progresiva de ganancias: el SL sube automáticamente a medida que el precio sube.")
            
            # --- ESCALONES ---
            st.markdown("## 📈 Sistema de Escalones")
            
            config['escalones_activo'] = st.checkbox(
                "Activar sistema de escalones", 
                config.get('escalones_activo', True),
                help="Cuando el precio sube y pasa un nivel Fibonacci, el Stop Loss sube automáticamente al nivel anterior. Así proteges las ganancias acumuladas."
            )
            
            if config['escalones_activo']:
                fib_options_escalon = [0.618, 0.5, 0.382, 0.236]
                config['escalon_activacion'] = st.select_slider(
                    "Nivel de activación",
                    options=fib_options_escalon,
                    value=config.get('escalon_activacion', 0.5),
                    help="¿A partir de qué nivel Fibonacci se activa la protección de escalones? Por defecto 0.5 (cuando ya tienes ganancia)."
                )
                
                st.markdown("---")
                
                config['escalones_ajustes_personalizados'] = st.checkbox(
                    "⚙️ Ajustes personalizados de escalón",
                    config.get('escalones_ajustes_personalizados', False),
                    help="Por defecto, los ajustes se heredan del Stop Loss normal. Activa esto para configurar ajustes diferentes para los escalones superiores."
                )
                
                if config['escalones_ajustes_personalizados']:
                    st.markdown("### 📐 Configuración SL Escalón Superior")
                    st.caption("Estos ajustes se aplican cuando el precio sube de escalón. Las bases suben automáticamente.")
                    
                    fib_options = [0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 0.886, 1.0]
                    
                    # Trigger Escalón
                    st.markdown("#### ⚡ Trigger Escalón")
                    col_et1, col_et2 = st.columns(2)
                    with col_et1:
                        config['escalon_trigger_base'] = st.selectbox(
                            "Base Trigger", 
                            fib_options, 
                            index=fib_options.index(config.get('escalon_trigger_base', 0.618)),
                            key="esc_trigger_base",
                            help="Nivel Fibonacci base para el trigger en escalón superior."
                        )
                    with col_et2:
                        adj_esc_trigger = st.slider(
                            "Ajuste (0 a -0.06)", 
                            0, 60, 
                            int(config.get('escalon_trigger_ajuste', 0.005) * 1000),
                            key="esc_trigger_adj",
                            help="Ajuste fino del trigger (se resta al nivel base)."
                        )
                        config['escalon_trigger_ajuste'] = adj_esc_trigger / 1000.0
                    st.caption(f"Nivel Final Trigger: {config['escalon_trigger_base'] - config['escalon_trigger_ajuste']:.4f}")
                    
                    # Rebote Escalón
                    st.markdown("#### 🏀 Rebote Escalón")
                    col_er1, col_er2 = st.columns(2)
                    with col_er1:
                        config['escalon_rebote_base'] = st.selectbox(
                            "Base Rebote", 
                            fib_options, 
                            index=fib_options.index(config.get('escalon_rebote_base', 0.5)),
                            key="esc_rebote_base",
                            help="Nivel Fibonacci base para el rebote en escalón superior."
                        )
                    with col_er2:
                        adj_esc_rebote = st.slider(
                            "Ajuste (0 a +0.025)", 
                            0, 25, 
                            int(config.get('escalon_rebote_ajuste', 0.011) * 1000),
                            key="esc_rebote_adj",
                            help="Ajuste fino del rebote (se suma al nivel base)."
                        )
                        config['escalon_rebote_ajuste'] = adj_esc_rebote / 1000.0
                    st.caption(f"Nivel Final Rebote: {config['escalon_rebote_base'] + config['escalon_rebote_ajuste']:.4f}")
                    
                    # S.L. Escalón
                    st.markdown("#### 💣 S.L. Escalón")
                    col_ed1, col_ed2 = st.columns(2)
                    with col_ed1:
                        config['escalon_definitivo_base'] = st.selectbox(
                            "Base S.L.", 
                            fib_options, 
                            index=fib_options.index(config.get('escalon_definitivo_base', 0.618)),
                            key="esc_def_base",
                            help="Nivel Fibonacci base para el S.L. en escalón superior."
                        )
                    with col_ed2:
                        adj_esc_def = st.slider(
                            "Ajuste (0 a +0.06)", 
                            0, 60, 
                            int(config.get('escalon_definitivo_ajuste', 0.005) * 1000),
                            key="esc_def_adj",
                            help="Ajuste fino del S.L. (se suma al nivel base)."
                        )
                        config['escalon_definitivo_ajuste'] = adj_esc_def / 1000.0
                    st.caption(f"Nivel Final S.L.: {config['escalon_definitivo_base'] + config['escalon_definitivo_ajuste']:.4f}")
                else:
                    st.info("ℹ️ **Modo heredado activo:** Los ajustes de SL se toman de la configuración de Stop Loss normal y se suben automáticamente en cada escalón.")
            
            st.markdown("---")
            
            # --- REENTRADAS PROGRESIVAS ---
            st.markdown("## 🎯 Reentradas Progresivas")
            
            config['reentradas_progresivas'] = st.checkbox(
                "Activar reentradas progresivas",
                config.get('reentradas_progresivas', False),
                help="En lugar de vender en el TP normal (0.382), el bot mantiene la posición y busca el TP máximo. El SL de escalón protege las ganancias si el precio cae."
            )
            
            if config['reentradas_progresivas']:
                tp_opciones = {
                    0.236: "0.236 (Conservador)",
                    0.0: "0.0 (P0 - Techo)",
                    -0.272: "1.272 (Extensión +27%)",
                    -0.618: "1.618 (Extensión +62%)"
                }
                tp_actual = config.get('tp_maximo_reentradas', -0.272)
                config['tp_maximo_reentradas'] = st.select_slider(
                    "TP Máximo con reentradas",
                    options=list(tp_opciones.keys()),
                    value=tp_actual,
                    format_func=lambda x: tp_opciones.get(x, str(x)),
                    help="¿Hasta dónde quieres surfear la tendencia? Niveles negativos son extensiones por encima del techo (P0)."
                )
                
                st.warning("⚠️ **Atención:** Con reentradas activas, NO vendes en el TP normal. Solo vendes cuando:\n"
                          "- El precio alcanza el TP máximo configurado, o\n"
                          "- El precio cae y toca el SL de escalón (saliendo con ganancia)")
            
            st.markdown("---")
            
            # Información visual
            st.markdown("### 📊 Ejemplo de funcionamiento")
            st.code("""
Escalón 0 (Entrada 0.618):
  └── SL Trigger: 0.786 → SL Rebote: 0.618 → S.L.: 0.791

Escalón +1 (Precio pasa 0.5):
  └── SL Trigger: 0.618 → SL Rebote: 0.5 → S.L.: 0.623
  └── ¡Ya proteges ganancia!

Escalón +2 (Precio pasa 0.382):  
  └── SL Trigger: 0.5 → SL Rebote: 0.382 → S.L.: 0.505
  └── ¡Ganancia asegurada si cae!

Con Reentradas: No vendes en 0.382, sigues hasta 1.272 (o donde configures)
            """, language=None)
            
            if st.button("💾 Guardar Escalones y Reentradas"):
                save_config(config)
                bot.reload_config()
                st.success("✅ Configuración guardada")
        
        # ============================================
        # 5. PROTECCIONES
        # ============================================
        with st.expander("6️⃣ Protecciones y Filtros", expanded=False):
            st.caption("Cortafuegos ante caídas de BTC, rachas de pérdidas, y monedas agotadas.")
            
            # --- PROTECCIÓN BTC ---
            st.markdown("## 📉 Protección BTC")
            st.caption("Si Bitcoin cae bruscamente, el mercado entero suele seguirlo. Esta protección actúa automáticamente.")
            
            config['proteccion_caida_btc'] = st.checkbox(
                "Activar Protección BTC", 
                config.get('proteccion_caida_btc', True),
                help="Activa los paracaídas automáticos cuando BTC cae. Recomendado: Siempre activado."
            )

            if config['proteccion_caida_btc']:
                st.markdown("### ⚡ Nivel 1: Alerta Moderada")
                st.caption("**Acción:** Muestra aviso en pantalla y ajusta los puntos de entrada a niveles más conservadores.")
                config['umbral_caida_moderada'] = st.slider(
                    "Caída Moderada (%)", -10.0, -1.0, 
                    config.get('umbral_caida_moderada', -3.0), 0.5,
                    help="Si BTC cae este porcentaje en 1 hora, se activa la alerta amarilla. Ejemplo: -3% es una caída moderada."
                )

                st.markdown("### 🛑 Nivel 2: Caída Fuerte")
                st.caption("**Acción:** Cierra automáticamente las posiciones que están en PÉRDIDAS. Las ganadoras se mantienen.")
                config['umbral_caida_fuerte'] = st.slider(
                    "Caída Fuerte (%)", -15.0, -3.0, 
                    config.get('umbral_caida_fuerte', -5.0), 0.5,
                    help="Si BTC cae este porcentaje, vende las operaciones que están en rojo para limitar pérdidas."
                )

                st.markdown("### 💣 Nivel 3: Caída Severa")
                st.caption("**Acción:** Vende TODO inmediatamente. Modo pánico.")
                config['umbral_caida_severa'] = st.slider(
                    "Caída Severa (%)", -20.0, -5.0, 
                    config.get('umbral_caida_severa', -7.0), 0.5,
                    help="Si BTC cae este porcentaje, vende absolutamente todo sin importar si está en ganancia o pérdida."
                )
            else:
                st.warning("⚠️ Protección BTC desactivada. El bot no reaccionará ante caídas de Bitcoin.")
            
            st.markdown("---")
            
            # --- PROTECCIÓN POR PÉRDIDAS ---
            st.markdown("## 🚨 Protección por Entradas Fallidas")
            st.caption("Si tienes muchas operaciones perdedoras seguidas, el bot se protege pasando a modo demo automáticamente.")
            
            config['proteccion_perdidas_activa'] = st.checkbox(
                "Activar Protección por Pérdidas", 
                config.get('proteccion_perdidas_activa', True),
                help="Si el porcentaje de pérdidas supera el umbral, cierra todas las posiciones y pasa a modo demo. Cuando mejore, vuelve a real automáticamente."
            )
            
            if config['proteccion_perdidas_activa']:
                col_prot1, col_prot2 = st.columns(2)
                
                with col_prot1:
                    config['ventana_operaciones'] = st.slider(
                        "Evaluar últimas N operaciones", 
                        3, 10, 
                        config.get('ventana_operaciones', 5), 1,
                        help="¿Cuántas operaciones recientes analizar para decidir si activar la protección? Ejemplo: 5 = mira las últimas 5 operaciones."
                    )
                
                with col_prot2:
                    config['umbral_perdidas_pct'] = st.slider(
                        "% Pérdidas para activar DEMO", 
                        50, 90, 
                        config.get('umbral_perdidas_pct', 75), 5,
                        help="Si este porcentaje de las últimas operaciones son pérdidas, activa el modo protección. Ejemplo: 75% = 3 de 4 operaciones perdedoras."
                    )
                
                config['proteccion_ops_para_volver'] = st.slider(
                    "Ops ganadoras en DEMO para volver a REAL", 
                    1, 5, 
                    config.get('proteccion_ops_para_volver', 1), 1,
                    help="Cuántas operaciones ganadoras necesita el bot en modo DEMO para volver automáticamente a REAL. Con 1 = la primera ganancia lo devuelve a REAL."
                )
                
                # Mostrar estado actual de protección
                if getattr(bot, 'modo_proteccion_activado', False):
                    ops_ganadas = getattr(bot, '_ops_ganadoras_proteccion', 0)
                    ops_necesarias = config.get('proteccion_ops_para_volver', 1)
                    st.warning(f"🛡️ **PROTECCIÓN ACTIVA** — {ops_ganadas}/{ops_necesarias} ops ganadoras para volver a REAL")
                
                st.info("📋 **¿Cómo funciona?**\n\n"
                       "1️⃣ Si X% de las últimas N operaciones son pérdidas → Cierra posiciones perdedoras y pasa a DEMO\n\n"
                       "2️⃣ El bot sigue operando normalmente pero con dinero virtual\n\n"
                       "3️⃣ Cuando consiga N operación(es) ganadora(s) → Vuelve automáticamente a REAL")
            else:
                st.warning("⚠️ Protección por pérdidas desactivada. El bot no se protegerá ante rachas perdedoras.")
            
            st.markdown("---")
            
            # =============================================
            # FILTRAR MONEDAS AGOTADAS
            # =============================================
            st.markdown("## 🚫 Filtrar Monedas Agotadas")
            st.caption("Si una moneda bajó casi al punto de compra pero no compró, y luego rebotó mucho, se considera 'agotada' y se descarta.")
            
            config['filtrar_monedas_agotadas'] = st.checkbox(
                "Activar Filtro de Monedas Agotadas", 
                config.get('filtrar_monedas_agotadas', True),
                help="Descarta monedas que ya tuvieron su oportunidad y rebotaron sin que entraras."
            )
            
            if config['filtrar_monedas_agotadas']:
                col_agot1, col_agot2 = st.columns(2)
                
                with col_agot1:
                    config['nivel_casi_compra'] = st.slider(
                        "📉 Nivel 'Casi Compra'", 
                        0.50, 0.80, 
                        config.get('nivel_casi_compra', 0.65), 
                        0.01,
                        format="%.2f",
                        help="Si el precio bajó hasta este nivel Fibonacci (cercano al de compra 0.618), se considera que 'casi compró'."
                    )
                
                with col_agot2:
                    config['nivel_rebote_agotado'] = st.slider(
                        "📈 Nivel 'Rebote Agotado'", 
                        0.30, 0.60, 
                        config.get('nivel_rebote_agotado', 0.45), 
                        0.01,
                        format="%.2f",
                        help="Si después de 'casi comprar' el precio sube pasando este nivel, la moneda se considera agotada."
                    )
                
                st.info(f"🔄 Si baja hasta **{config['nivel_casi_compra']:.2f}** y luego sube hasta **{config['nivel_rebote_agotado']:.2f}** → se cancela la orden.")
            
            st.markdown("---")
            
            # OTROS FILTROS DE PROTECCIÓN
            st.markdown("## 🔧 Otros Filtros")
            
            col_filtros1, col_filtros2 = st.columns(2)
            with col_filtros1:
                config['usar_blacklist_temporal'] = st.checkbox(
                    "📛 Blacklist Temporal", 
                    config.get('usar_blacklist_temporal', True),
                    help="No comprar monedas que nos han hecho perder dinero recientemente."
                )
            with col_filtros2:
                config['usar_fib_magnetico'] = st.checkbox(
                    "🧲 Fibonacci Magnético", 
                    config.get('usar_fib_magnetico', True),
                    help="Ajusta niveles Fib a soportes/resistencias reales del mercado."
                )
            
            if config.get('usar_fib_magnetico', True):
                st.markdown("---")
                st.markdown("##### 🧲 Fibonacci Magnético")
                st.caption("Ajusta los niveles para que se apoyen en zonas reales de soporte/resistencia donde el precio ha rebotado.")
                
                config['usar_magnetico_p0p1'] = st.checkbox(
                    "🎯 Ajuste Magnético P0/P1",
                    config.get('usar_magnetico_p0p1', True),
                    help="Mueve P0 y/o P1 a niveles de soporte/resistencia reales."
                )
                
                if config.get('usar_magnetico_p0p1', True):
                    col_mag_p1, col_mag_p0 = st.columns(2)
                    with col_mag_p1:
                        config['usar_magnetico_p1'] = st.checkbox(
                            "⬇️ Ajustar P1 (suelo)",
                            config.get('usar_magnetico_p1', True),
                            help="Mueve P1 al soporte más fuerte cercano."
                        )
                        if config.get('usar_magnetico_p1', True):
                            config['magnetico_p1_bidireccional'] = st.checkbox(
                                "↕️ P1 bidireccional",
                                config.get('magnetico_p1_bidireccional', True),
                                help="Si activado: P1 puede subir O bajar al soporte más fuerte (rango se expande o reduce). "
                                     "Si desactivado: P1 solo sube (rango solo se reduce)."
                            )
                    with col_mag_p0:
                        config['usar_magnetico_p0'] = st.checkbox(
                            "⬆️ Ajustar P0 (techo)",
                            config.get('usar_magnetico_p0', True),
                            help="Mueve P0 a la resistencia más fuerte. Desactiva si quieres mantener el máximo real."
                        )
                
                config['usar_tp_dinamico'] = st.checkbox(
                    "🚀 TP Dinámico (ajustar TP durante la posición)",
                    config.get('usar_tp_dinamico', True),
                    help="Mientras la posición está abierta, el TP se ajusta a las resistencias reales del momento. "
                         "Si hay un techo fuerte antes del TP teórico, vende ahí. Si el precio supera el TP y tiene camino libre, lo extiende."
                )
                
                col_mag1, col_mag2 = st.columns(2)
                with col_mag1:
                    config['tolerancia_magnetica_p0p1'] = st.slider(
                        "Movimiento máx P0/P1 (% del rango)",
                        10, 40,
                        int(config.get('tolerancia_magnetica_p0p1', 0.30) * 100),
                        5,
                        help="Cuánto se permite mover P0/P1 como % del rango total. "
                             "30% = si el rango es $0.20, P1 puede subir hasta $0.06 para apoyarse en un soporte real."
                    ) / 100
                with col_mag2:
                    config['tolerancia_magnetica'] = st.slider(
                        "Tolerancia Entry/TP (%)",
                        0.0, 2.0,
                        config.get('tolerancia_magnetica', 0.02) * 100,
                        0.1,
                        format="%.1f%%",
                        help="Ajuste fino adicional sobre Entry y TP después de calcular Fibonacci."
                    ) / 100
                
                if config.get('usar_magnetico_p0p1', True):
                    st.markdown("""
                    <div style='background: #1a1a2e; border-radius: 8px; padding: 10px; margin: 8px 0; font-size: 0.82em; color: #eee;'>
                    <b>¿Cómo funciona?</b><br/>
                    1️⃣ El bot encuentra P1 (suelo) y P0 (techo) matemáticos<br/>
                    2️⃣ Busca zonas donde muchas velas han tocado y rebotado<br/>
                    3️⃣ <b>⬇️ P1:</b> Si hay soporte fuerte cerca → mueve P1 ahí. Con bidireccional, puede bajar a un suelo histórico más profundo<br/>
                    4️⃣ <b>⬆️ P0:</b> Si hay resistencia fuerte cerca → baja P0. Desactívalo para usar siempre el máximo real<br/>
                    <br/>
                    <b>Ejemplo THEUSDC:</b> Bot pone P0=0.2798 (resistencia). Con P0 desactivado: P0=0.2833 (máximo real) → TP más alto.<br/>
                    Con P1 bidireccional: P1 baja a 0.2558 (soporte histórico) en vez de 0.2581 (spike) → rango más amplio.<br/>
                    <br/>
                    <b>🚀 TP Dinámico:</b> Si después de comprar aparece un techo fuerte antes del TP → vende ahí.<br/>
                    Si el precio rompe el TP → extiende al siguiente techo.
                    </div>
                    """, unsafe_allow_html=True)
            
            if st.button("💾 Guardar Protecciones"):
                save_config(config)
                bot.reload_config()
                st.success("✅ Protecciones guardadas")

        # ============================================
        # 7. ANÁLISIS TÉCNICO
        # ============================================
        with st.expander("7️⃣ Análisis Técnico", expanded=False):
            st.caption("Indicadores que filtran malas entradas y priorizan las buenas en el score.")
            
            # =============================================
            # INDICADORES DE TENDENCIA
            # =============================================
            
            # RSI
            st.markdown("##### 📈 RSI (Relative Strength Index)")
            col_rsi1, col_rsi2 = st.columns(2)
            with col_rsi1:
                config['usar_filtro_rsi'] = st.checkbox(
                    "Activar filtro RSI",
                    config.get('usar_filtro_rsi', True),
                    help="El RSI mide si una moneda está sobrecomprada (>70) o sobrevendida (<30). El bot evitará comprar monedas sobrecompradas."
                )
            with col_rsi2:
                if config['usar_filtro_rsi']:
                    config['rsi_max_compra'] = st.slider(
                        "RSI máximo para comprar",
                        40, 80,
                        config.get('rsi_max_compra', 65),
                        help="No comprará si el RSI supera este valor. Menor = más exigente. 65 es un buen balance."
                    )
            
            if config.get('usar_filtro_rsi', True):
                col_rsi3, col_rsi4 = st.columns(2)
                with col_rsi3:
                    config['rsi_periodo'] = st.slider(
                        "Periodo RSI",
                        7, 21,
                        config.get('rsi_periodo', 14),
                        help="Velas usadas para calcular RSI. 14 es el estándar."
                    )
                with col_rsi4:
                    config['rsi_peso_score'] = st.slider(
                        "Peso RSI en Score (%)",
                        0, 30,
                        int(config.get('rsi_peso_score', 0.15) * 100),
                        help="Cuánto influye el RSI en la puntuación total."
                    ) / 100
            
            st.markdown("---")
            
            # Confirmación de Volumen
            st.markdown("##### 📊 Confirmación de Volumen")
            col_vol_c1, col_vol_c2 = st.columns(2)
            with col_vol_c1:
                config['usar_confirmacion_volumen'] = st.checkbox(
                    "Activar confirmación de volumen",
                    config.get('usar_confirmacion_volumen', True),
                    help="Verifica que el volumen actual sea superior a la media. Más volumen = más convicción en el movimiento."
                )
            with col_vol_c2:
                if config['usar_confirmacion_volumen']:
                    config['volumen_ratio_minimo'] = st.slider(
                        "Ratio volumen mínimo",
                        1.0, 3.0,
                        config.get('volumen_ratio_minimo', 1.2),
                        0.1,
                        help="El volumen actual debe ser X veces la media. 1.2 = 20% más que la media."
                    )
            
            st.markdown("---")
            
            # EMA Tendencia
            st.markdown("##### 📉 Filtro EMA Tendencia")
            config['usar_filtro_ema_tendencia'] = st.checkbox(
                "Activar filtro EMA",
                config.get('usar_filtro_ema_tendencia', True),
                help="Usa el cruce de EMAs (rápida vs lenta) para detectar tendencia. Penaliza monedas en tendencia bajista."
            )
            
            if config['usar_filtro_ema_tendencia']:
                col_ema1, col_ema2 = st.columns(2)
                with col_ema1:
                    config['ema_rapida'] = st.slider(
                        "EMA rápida (periodos)",
                        3, 15,
                        config.get('ema_rapida', 8),
                        help="EMA de corto plazo. Más bajo = más sensible."
                    )
                with col_ema2:
                    config['ema_lenta'] = st.slider(
                        "EMA lenta (periodos)",
                        15, 50,
                        config.get('ema_lenta', 21),
                        help="EMA de largo plazo. La tendencia es alcista cuando la rápida está por encima."
                    )
            
            st.markdown("---")
            
            # =============================================
            # DETECCIÓN DE PATRÓN V-RECOVERY
            # =============================================
            st.markdown("#### 🔍 Detección de Patrón (V-Recovery)")
            st.caption("El bot analiza la forma del rebote (V rápida, U lenta, gradual...) y ajusta automáticamente los niveles de entrada y TP para adaptarse al movimiento.")
            
            col_pat1, col_pat2 = st.columns(2)
            with col_pat1:
                config['usar_deteccion_patron'] = st.checkbox(
                    "Activar detección de patrón",
                    config.get('usar_deteccion_patron', True),
                    help="Analiza si el rebote fue en V (rápido), U (lento), o gradual. Cada patrón tiene niveles óptimos diferentes."
                )
            with col_pat2:
                if config['usar_deteccion_patron']:
                    config['patron_ajuste_automatico'] = st.checkbox(
                        "Ajuste automático de Fibonacci",
                        config.get('patron_ajuste_automatico', True),
                        help="Permite que el patrón detectado modifique automáticamente los niveles de entrada y TP."
                    )
            
            if config.get('usar_deteccion_patron', True):
                if config.get('patron_ajuste_automatico', True):
                    st.markdown("##### Niveles Fibonacci por patrón")
                    st.caption("Modifica la entrada y TP que usa cada patrón detectado.")
                    
                    fib_opts = [0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 0.886, 1.0]
                    patrones_cfg = [
                        ("🔴 V_SHARP", "V_SHARP", "Rebote violento"),
                        ("🟠 V_NORMAL", "V_NORMAL", "Rebote moderado"),
                        ("🟢 U_SHAPE", "U_SHAPE", "Consolidación"),
                        ("⚪ GRADUAL", "GRADUAL", "Subida lenta"),
                        ("🔵 L_SHAPE", "L_SHAPE", "Sin rebote"),
                    ]
                    
                    col_lbl, col_ent, col_tp = st.columns([1.2, 1, 1])
                    with col_lbl:
                        st.markdown("**Patrón**")
                    with col_ent:
                        st.markdown("**Entrada**")
                    with col_tp:
                        st.markdown("**TP**")
                    
                    for label, key, desc in patrones_cfg:
                        col_l, col_e, col_t = st.columns([1.2, 1, 1])
                        with col_l:
                            st.markdown(f"{label}")
                        with col_e:
                            val_e = config.get(f'patron_fib_{key}_entry', 0.618)
                            closest_e = min(fib_opts, key=lambda x: abs(x - val_e))
                            config[f'patron_fib_{key}_entry'] = st.selectbox(
                                f"E {key}", fib_opts, 
                                index=fib_opts.index(closest_e),
                                key=f"pat_e_{key}", label_visibility="collapsed"
                            )
                        with col_t:
                            val_t = config.get(f'patron_fib_{key}_tp', 0.382)
                            closest_t = min(fib_opts, key=lambda x: abs(x - val_t))
                            config[f'patron_fib_{key}_tp'] = st.selectbox(
                                f"T {key}", fib_opts,
                                index=fib_opts.index(closest_t),
                                key=f"pat_t_{key}", label_visibility="collapsed"
                            )
                else:
                    st.markdown("""
                    <div style='background: #1a1a2e; border-radius: 8px; padding: 12px; margin: 8px 0; font-size: 0.85em;'>
                    <table style='width:100%; color: #eee;'>
                    <tr><th>Patrón</th><th>Lógica</th></tr>
                    <tr><td>🔴 <b>V_SHARP</b></td><td>Rebote violento</td></tr>
                    <tr><td>🟠 <b>V_NORMAL</b></td><td>Rebote moderado</td></tr>
                    <tr><td>🟢 <b>U_SHAPE</b></td><td>Consolidación previa</td></tr>
                    <tr><td>⚪ <b>GRADUAL</b></td><td>Subida lenta</td></tr>
                    <tr><td>🔵 <b>L_SHAPE</b></td><td>Sin rebote claro</td></tr>
                    </table>
                    </div>
                    """, unsafe_allow_html=True)
            
            st.markdown("---")
            
            # =============================================
            # ESTRUCTURA HH/HL Y DOBLE SUELO
            # =============================================
            st.markdown("#### 📈 Estructura de Mercado (HH/HL)")
            st.caption("Analiza si los máximos y mínimos son cada vez más altos (tendencia alcista) o más bajos (tendencia bajista). Es el indicador más fiable de tendencia.")
            
            config['usar_filtro_hhhl'] = st.checkbox(
                "Activar análisis HH/HL",
                config.get('usar_filtro_hhhl', True),
                help="HH/HL = Higher Highs / Higher Lows → tendencia alcista. LH/LL = Lower Highs / Lower Lows → bajista. Si es BAJISTA_FUERTE, no compra."
            )
            
            if config.get('usar_filtro_hhhl', True):
                st.markdown("""
                <div style='background: #1a1a2e; border-radius: 8px; padding: 10px; margin: 8px 0; font-size: 0.82em;'>
                <table style='width:100%; color: #eee;'>
                <tr><th>Estructura</th><th>Significado</th><th>Acción</th></tr>
                <tr><td>📈📈 <b>ALCISTA_FUERTE</b></td><td>Todos los máx y mín suben</td><td>Score +100 (ideal)</td></tr>
                <tr><td>📈 <b>ALCISTA</b></td><td>Mayoría suben</td><td>Score +75</td></tr>
                <tr><td>➡️ <b>LATERAL</b></td><td>Sin tendencia clara</td><td>Score neutral</td></tr>
                <tr><td>📉 <b>BAJISTA</b></td><td>Mayoría bajan</td><td>Score bajo, precaución</td></tr>
                <tr><td>📉📉 <b>BAJISTA_FUERTE</b></td><td>Todos bajan</td><td><b>🚫 NO COMPRA</b></td></tr>
                <tr><td>🔄 <b>GIRO_BAJISTA</b></td><td>Máximo decreciente</td><td><b>🚫 NO COMPRA</b></td></tr>
                </table>
                <br/>
                <b>🔄 Doble Suelo (W):</b> Si el precio toca el mismo soporte 2 veces → soporte MUY fuerte. Bonus +5 al score.
                </div>
                """, unsafe_allow_html=True)
                
                config['hhhl_bloquear_bajista_fuerte'] = st.checkbox(
                    "Bloquear GIRO_BAJISTA (máximo decreciente)",
                    config.get('hhhl_bloquear_bajista_fuerte', True),
                    help="No comprar si el precio hace un máximo más bajo que el anterior. Señal clásica de cambio de tendencia bajista."
                )
            
            st.markdown("---")
            
            # =============================================
            # PUMP EXHAUSTION
            # =============================================
            st.markdown("#### 🚀 Filtro Pump Exhaustion")
            st.caption("No comprar monedas que ya han subido demasiado en 24h. Después de un pump, el riesgo de corrección es muy alto.")
            
            config['max_subida_24h_compra'] = st.slider(
                "Máxima subida 24h para comprar (%)", 10.0, 80.0,
                config.get('max_subida_24h_compra', 30.0), 5.0,
                help="Si una moneda ha subido más de este % en las últimas 24h, NO se compra. Ejemplo: ORCA subió 51.8% → con límite de 30% se bloquearía."
            )
            
            st.markdown("---")
            
            # =============================================
            # LOWER HIGH
            # =============================================
            st.markdown("#### 📉 Filtro Lower High")
            config['filtrar_lower_high'] = st.checkbox(
                "Bloquear si P0 < máximo previo (Lower High)",
                config.get('filtrar_lower_high', True),
                help="No comprar si el techo actual (P0) es significativamente más bajo que un máximo anterior. Indica que la tendencia está girando a bajista."
            )
            
            if st.button("💾 Guardar Análisis Técnico"):
                save_config(config)
                bot.reload_config()
                st.success("✅ Análisis técnico guardado")

        # ============================================
        # 8. SWAP INTELIGENTE
        # ============================================
        with st.expander("8️⃣ Swap Inteligente", expanded=False):
            st.caption("Cambia automáticamente una posición mediocre por una oportunidad mucho mejor.")
            config['swap_automatico'] = st.checkbox(
                "Activar SWAP", 
                config.get('swap_automatico', False),
                help="Si tienes una operación que va mal y aparece otra oportunidad muchísimo mejor, ¿cambiamos la mala por la buena?"
            )
            config['swap_min_score_diferencia'] = st.slider(
                "Diferencia Score Min", 5.0, 50.0, 
                config.get('swap_min_score_diferencia', 15.0),
                help="¿Cuánto mejor tiene que ser la nueva oportunidad para justificar el cambio?"
            )
            config['swap_min_ganancia_actual'] = st.slider(
                "Ganancia Max para Swap %", -10.0, 100.0, 
                config.get('swap_min_ganancia_actual', 50.0),
                help="Solo hacer swap si la operación actual NO ha ganado más de este %."
            )
            
            if st.button("💾 Guardar Swap", help="Guarda la configuración de Swap Inteligente."):
                save_config(config)
                bot.reload_config()
                st.success("✅ Configuración de Swap guardada")

        with st.expander("9️⃣ APIs y Conexión", expanded=False):
            st.caption("Claves de Binance y Telegram. En modo demo no son necesarias.")
            config['binance_api_key'] = st.text_input(
                "Binance API Key", 
                config.get('binance_api_key', ''), 
                type="password",
                help="La llave pública que te da Binance. Necesaria para operar."
            )
            config['binance_api_secret'] = st.text_input(
                "Binance API Secret", 
                config.get('binance_api_secret', ''), 
                type="password",
                help="La llave privada secreta. ¡NUNCA la compartas!"
            )
            
            st.markdown("##### 🔄 Sincronización con Binance")
            config['sync_interval_minutos'] = st.slider(
                "Intervalo de sync (minutos)", 5, 60,
                config.get('sync_interval_minutos', 10), 5,
                help="Cada cuántos minutos el bot consulta Binance para detectar tokens/órdenes huérfanas. También se ejecuta siempre al arrancar."
            )
            config['telegram_bot_token'] = st.text_input(
                "Telegram Token", 
                config.get('telegram_bot_token', ''), 
                type="password",
                help="El código de tu bot de Telegram (lo que te dio @BotFather)."
            )
            config['telegram_chat_id'] = st.text_input(
                "Telegram Chat ID", 
                config.get('telegram_chat_id', ''),
                help="Tu ID de usuario de Telegram (para que el bot sepa a quién escribir)."
            )
            
            if config.get('telegram_bot_token') and config.get('telegram_chat_id'):
                if st.button("🧪 Test Telegram"):
                    with st.spinner("Enviando test..."):
                        result = test_telegram_connection(config['telegram_bot_token'], config['telegram_chat_id'])
                        if result.get('success'):
                            st.success(result['message'])
                        else:
                            st.error(result['message'])
            
            if st.button("💾 Guardar APIs", help="Guarda las claves de API."):
                save_config(config)
                bot.reload_config()
                st.success("✅ Claves de API guardadas")

        with st.expander("🔔 Notificaciones Telegram", expanded=False):
            st.caption("Configura qué eventos quieres recibir por Telegram.")
            
            if not config.get('telegram_bot_token') or not config.get('telegram_chat_id'):
                st.warning("⚠️ Configura Token y Chat ID en 'APIs y Conexión' primero")
            
            col_n1, col_n2 = st.columns(2)
            with col_n1:
                config['telegram_notif_compras'] = st.checkbox(
                    "🟢 Compras", config.get('telegram_notif_compras', True),
                    help="Notificar cuando el bot compra una moneda"
                )
                config['telegram_notif_ventas'] = st.checkbox(
                    "🔴 Ventas", config.get('telegram_notif_ventas', True),
                    help="Notificar cuando el bot vende (TP, SL, manual...)"
                )
                config['telegram_notif_ordenes'] = st.checkbox(
                    "📤 Órdenes colocadas", config.get('telegram_notif_ordenes', True),
                    help="Notificar cuando se coloca una LIMIT BUY en Binance"
                )
                config['telegram_notif_upgrades'] = st.checkbox(
                    "🔄 Upgrades", config.get('telegram_notif_upgrades', True),
                    help="Notificar cuando se reemplaza una orden por otra mejor"
                )
            with col_n2:
                config['telegram_notif_proteccion'] = st.checkbox(
                    "🛡️ Protección", config.get('telegram_notif_proteccion', True),
                    help="Notificar cuando se activa/desactiva la protección por pérdidas"
                )
                config['telegram_notif_btc_crash'] = st.checkbox(
                    "🚨 Caída BTC", config.get('telegram_notif_btc_crash', True),
                    help="Notificar alertas de caída de Bitcoin"
                )
                config['telegram_notif_modo'] = st.checkbox(
                    "🔀 Cambio de Modo", config.get('telegram_notif_modo', True),
                    help="Notificar cuando cambia entre DEMO y REAL"
                )
                config['telegram_notif_errores'] = st.checkbox(
                    "❌ Errores", config.get('telegram_notif_errores', False),
                    help="Notificar errores críticos del bot (puede generar muchos mensajes)"
                )
            
            if st.button("💾 Guardar Notificaciones"):
                save_config(config)
                bot.reload_config()
                st.success("✅ Notificaciones guardadas")
    
    # ============================================
    # CONTENIDO PRINCIPAL
    # ============================================
    
    # Reloj UTC arriba a la izquierda, encima del título
    import streamlit.components.v1 as components
    components.html("""
    <div style="text-align: left; padding: 0;">
        <span id="reloj-utc" style="margin: 0; color: #262730; font-size: 20px; font-weight: bold; font-family: monospace;">--:--:-- UTC+1</span>
    </div>
    <script>
    function actualizarReloj() {
        const ahora = new Date();
        // UTC+1 (hora Europa Central)
        const utc1 = new Date(ahora.getTime() + 3600000);
        const horas = String(utc1.getUTCHours()).padStart(2, '0');
        const minutos = String(utc1.getUTCMinutes()).padStart(2, '0');
        const segundos = String(utc1.getUTCSeconds()).padStart(2, '0');
        document.getElementById('reloj-utc').innerHTML = horas + ':' + minutos + ':' + segundos + ' UTC+1';
    }
    setInterval(actualizarReloj, 1000);
    actualizarReloj();
    </script>
    """, height=35)
    
    # Título + Indicador de Modo
    col_titulo, col_modo = st.columns([4, 1])
    with col_titulo:
        st.title("🚀 TradingBro 1.0 - Bot Dinámico Fibonacci")
    with col_modo:
        es_demo = config.get('modo_demo', True)
        es_proteccion = getattr(bot, 'modo_proteccion_activado', False)
        
        if es_proteccion:
            modo_label = "🛡️ PROTECCIÓN"
            modo_color = "#FF6B35"
        elif es_demo:
            modo_label = "🎮 DEMO"
            modo_color = "#FFA500"
        else:
            modo_label = "💰 REAL"
            modo_color = "#00C851"
        
        st.markdown(f"""
        <div style="text-align:center; padding:8px; margin-top:12px; 
                    background:{modo_color}22; border:2px solid {modo_color}; 
                    border-radius:8px; font-weight:bold; color:{modo_color}; font-size:1.1em;">
            {modo_label}
        </div>
        """, unsafe_allow_html=True)
        
        if st.button("🔄 Cambiar Modo", use_container_width=True, 
                     help="Alterna entre DEMO y REAL. Si hay protección activa, la resetea."):
            nuevo_modo = bot.toggle_modo()
            config['modo_demo'] = nuevo_modo
            st.rerun()
    
    # Alertas BTC (solo si hay alerta)
    estado = bot.get_estado()
    if estado['btc_status'] and estado['btc_status'].get('nivel_alerta') != 'NORMAL':
        nivel = estado['btc_status']['nivel_alerta']
        msg = f"{'🚨' if nivel=='SEVERA' else '⚠️' if nivel=='FUERTE' else 'ℹ️'} **ALERTA BTC {nivel}**: "
        msg += f"{estado['btc_status'].get('caida_1h', 0)}% (1h)"
        (st.error if nivel=='SEVERA' else st.warning if nivel=='FUERTE' else st.info)(msg)
    
    # ============================================
    # GRÁFICO FIBONACCI (ancho completo)
    # ============================================
    with st.spinner("Cargando gráfico..."):
        fig = generar_grafico_fibonacci(bot.market)
        if fig:
            st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("---")
    
    # ============================================
    # TABS PRINCIPALES
    # ============================================
    tab1, tab2, tab4, tab5 = st.tabs(["🎯 Oportunidades", "💰 Trades", "📈 Estadísticas", "📜 Logs"])
    
    # TAB 1: OPORTUNIDADES
    with tab1:
        st.header("🎯 Oportunidades de Compra")
        
        oportunidades = estado['oportunidades']
        min_score = config.get('min_score_compra', 60)
        
        col_1h, col_4h, col_1d = st.columns(3)
        lista_columnas = [col_1h, col_4h, col_1d]
        tiempos = ['1h', '4h', '1d']
        velas_usadas = {'1h': '5m', '4h': '15m', '1d': '1h'}
        
        for i in range(3):
            with lista_columnas[i]:
                st.markdown(f"### ⏰ {tiempos[i]}")
                st.caption(f"📊 Usa velas de **{velas_usadas[tiempos[i]]}**")
                
                ops_filtradas = [op for op in oportunidades if op['timeframe'] == tiempos[i] and op['score'] >= min_score]
                
                if not ops_filtradas:
                    st.caption("Sin datos")
                else:
                    for op in ops_filtradas:
                        simbolo = op['symbol']
                        score = op.get('score', 0)
                        subida_24h = op.get('subida_24h', 0)
                        
                        # Color de subida: verde si positiva, rojo si negativa
                        color_subida = "#28a745" if subida_24h >= 0 else "#dc3545"
                        signo_subida = "+" if subida_24h >= 0 else ""
                        
                        # RSI info
                        rsi_val = op.get('analysis', {}).get('rsi', {}).get('rsi', 0)
                        rsi_color = "#28a745" if rsi_val < 40 else ("#dc3545" if rsi_val > 60 else "#6c757d")
                        rsi_text = f"<span style='color:{rsi_color}; font-size:0.75em;'>RSI:{rsi_val:.0f}</span>" if rsi_val else ""
                        
                        # Pattern info
                        patron_op = op.get('analysis', {}).get('patron_recuperacion', '')
                        patron_emojis = {'V_SHARP': '🔴V', 'V_NORMAL': '🟠V', 'U_SHAPE': '🟢U', 'GRADUAL': '⚪G', 'L_SHAPE': '🔵L'}
                        patron_text = f"<span style='font-size:0.75em;'>{patron_emojis.get(patron_op, '')}</span>" if patron_op and patron_op != 'DESCONOCIDO' else ""
                        
                        # HH/HL info
                        estructura_op = op.get('analysis', {}).get('estructura_hhhl', '')
                        est_emojis = {'ALCISTA_FUERTE': '📈📈', 'ALCISTA': '📈', 'LATERAL': '➡️', 'BAJISTA': '📉', 'BAJISTA_FUERTE': '📉📉'}
                        est_text = f"<span style='font-size:0.75em;'>{est_emojis.get(estructura_op, '')}</span>" if estructura_op and estructura_op != 'INDEFINIDO' else ""
                        
                        # Doble suelo
                        ds_text = "<span style='font-size:0.75em; color:#00ff00;'>W</span>" if op.get('analysis', {}).get('doble_suelo', False) else ""
                        
                        # TradingView URL - usar intervalo de VELAS (no timeframe)
                        tf_map_op = {'1m': '1', '5m': '5', '15m': '15', '30m': '30', '1h': '60', '4h': '240', '1d': 'D', '1w': 'W'}
                        vela_interval = velas_usadas.get(tiempos[i], tiempos[i])
                        tv_int = tf_map_op.get(vela_interval, '60')
                        tv_url_op = f"https://www.tradingview.com/chart/?symbol=BINANCE%3A{simbolo}&interval={tv_int}"
                        
                        st.markdown(f"""
                        <div style="padding: 4px 0; border-bottom: 1px solid #eee; display: flex; justify-content: space-between; align-items: center;">
                            <a href="{tv_url_op}" target="_blank" style="text-decoration:none; font-size:0.8em;" title="Abrir en TradingView">📈</a>
                            <strong>{simbolo}</strong>
                            {rsi_text} {patron_text} {est_text} {ds_text}
                            <span style="color: {color_subida}; font-weight: bold;">{signo_subida}{subida_24h:.1f}%</span>
                            <span style="background-color: #f0f0f0; padding: 2px 6px; border-radius: 4px;">🎯 {score:.0f}</span>
                        </div>
                        """, unsafe_allow_html=True)

    # TAB 2: MIS TRADES
    with tab2:
        st.header("💰 Trades")
        
        ordenes_pendientes = estado['ordenes_pendientes']
        posiciones_activas = estado['open_positions']
        
        lista_unificada = []
        
        for key, ord_val in ordenes_pendientes.items():
            ord_val['tipo_item'] = 'pendiente'
            lista_unificada.append(ord_val)
            
        for key, pos_val in posiciones_activas.items():
            pos_val['tipo_item'] = 'activa'
            lista_unificada.append(pos_val)
            
        # Ordenar: primero activas, luego pendientes, dentro de cada grupo por score
        lista_unificada.sort(key=lambda x: (0 if x.get('tipo_item') == 'activa' else 1, -x.get('score', 0)))

        if not lista_unificada:
            st.info("📭 No tienes trades activos ni pendientes.")
        else:
            card_style = """
            <div style="
                border: 1px solid #d0d0d0; 
                border-radius: 8px; 
                padding: 15px; 
                margin-bottom: 10px; 
                background-color: #fafafa;
            ">
            """
            close_div = "</div>"

            for item in lista_unificada:
                es_activa = item.get('tipo_item') == 'activa'
                analysis = item.get('analysis', {})
                
                es_oco_externa = es_activa and item.get('_oco_externa', False)
                if es_oco_externa:
                    color_borde = "#1a6fa8"
                else:
                    color_borde = "#28a745" if es_activa else "#ffc107"
                modo_item = item.get('modo', 'DEMO')
                modo_tag = " 🔴REAL" if modo_item == 'REAL' else ""
                oco_tag = " 🛡️OCO" if item.get('binance_oco_id') and not es_oco_externa else ""
                binance_tag = " 📤BIN" if item.get('binance_order_id') else ""
                if es_oco_externa:
                    estado_texto = f"🔗 OCO BINANCE{modo_tag}"
                else:
                    estado_texto = f"🟢 ACTIVA{modo_tag}{oco_tag}" if es_activa else f"🟡 PENDIENTE{modo_tag}{binance_tag}"
                
                st.markdown(f"""
                <div style="
                    border: 2px solid {color_borde}; 
                    border-radius: 8px; 
                    padding: 15px; 
                    margin-bottom: 10px; 
                    background-color: #fafafa;
                ">
                """, unsafe_allow_html=True)

                cols_header = st.columns([2.5, 0.4, 0.8, 1.2, 0.8, 1])
                with cols_header[0]:
                    # Moneda clickable - al pulsar selecciona en Niveles del Trade
                    sym_item = item.get('symbol', '')
                    prefix_niv = "🟢" if es_activa else "🟡"
                    if st.button(f"**{sym_item}**", key=f"niveles_{sym_item}", help=f"Ver {sym_item} en Niveles del Trade"):
                        st.session_state['selected_trade_symbol'] = f"{prefix_niv} {sym_item}"
                        st.rerun()
                with cols_header[1]:
                    # Botón TradingView - usar intervalo de VELAS (no timeframe)
                    symbol_item = item.get('symbol', '')
                    tf_item = item.get('timeframe', '1h')
                    velas_map = {'1h': '5m', '4h': '15m', '1d': '1h', '1w': '4h'}
                    # Usar config_temporalidades si existe, sino fallback
                    temp_cfg = config.get('config_temporalidades', {}).get(tf_item, {})
                    vela_real = temp_cfg.get('velas', velas_map.get(tf_item, tf_item))
                    tf_map = {'1m': '1', '5m': '5', '15m': '15', '30m': '30', '1h': '60', '4h': '240', '1d': 'D', '1w': 'W'}
                    tv_interval = tf_map.get(vela_real, '60')
                    tv_symbol = symbol_item.replace('USDC', 'USDC')
                    tv_url = f"https://www.tradingview.com/chart/?symbol=BINANCE%3A{tv_symbol}&interval={tv_interval}"
                    st.link_button("📈", tv_url, help=f"Abrir {symbol_item} en TradingView ({vela_real})")
                with cols_header[2]:
                    # Botón cerrar/cancelar
                    if es_activa:
                        if item.get('_oco_externa'):
                            st.markdown("🔗", help="OCO activa en Binance — gestiona desde Binance")
                        elif st.button("❌ Cerrar", key=f"cerrar_{symbol_item}", help="Cierra esta posición manualmente al precio actual"):
                            bot.cerrar_posicion_manual(symbol_item)
                            st.rerun()
                    else:
                        if st.button("🗑️ Cancelar", key=f"cancelar_{symbol_item}", help="Cancela esta orden pendiente"):
                            bot.cancelar_orden_manual(symbol_item)
                            st.rerun()
                with cols_header[3]:
                    st.markdown(f"**{estado_texto}**")
                with cols_header[4]:
                    st.markdown(f"⏰ {item.get('timeframe', '1h')}")
                with cols_header[5]:
                    st.markdown(f"📊 Score: **{item.get('score', 0):.1f}**")

                # Mostrar indicadores
                rsi_info = analysis.get('rsi', {})
                ema_info = analysis.get('ema', {})
                entrada_motivo = analysis.get('entrada_ajustada_motivo')
                patron = analysis.get('patron_recuperacion', '')
                patron_det = analysis.get('patron_info', {})
                estructura = analysis.get('estructura_hhhl', '')
                hhhl_det = analysis.get('hhhl_info', {})
                doble_suelo = analysis.get('doble_suelo', False)
                
                indicadores_text = []
                if rsi_info:
                    rsi_val = rsi_info.get('rsi', 0)
                    rsi_zona = rsi_info.get('zona', '')
                    color_rsi = '#28a745' if rsi_val < 40 else ('#dc3545' if rsi_val > 60 else '#6c757d')
                    indicadores_text.append(f"<span style='color:{color_rsi}'>RSI:{rsi_val:.0f}</span>")
                if ema_info:
                    tend = "↑" if ema_info.get('tendencia_alcista') else "↓"
                    color_ema = '#28a745' if ema_info.get('tendencia_alcista') else '#dc3545'
                    indicadores_text.append(f"<span style='color:{color_ema}'>EMA{tend}</span>")
                
                # Patrón: solo mostrar si cambió niveles (V_SHARP, V_NORMAL, L_SHAPE)
                if patron and patron not in ('DESCONOCIDO', 'GRADUAL', 'U_SHAPE'):
                    colores_patron = {'V_SHARP': '#ff4500', 'V_NORMAL': '#ff8c00', 'L_SHAPE': '#dc3545'}
                    color_p = colores_patron.get(patron, '#6c757d')
                    entry_adj = patron_det.get('ajuste_entry', 0)
                    tp_adj = patron_det.get('ajuste_tp', 0)
                    indicadores_text.append(f"<span style='color:{color_p}'>🔍{patron} Fib:{entry_adj}/{tp_adj}</span>")
                elif patron in ('GRADUAL', 'U_SHAPE'):
                    indicadores_text.append(f"<span style='color:#6c757d'>🔍{patron}</span>")
                
                # HH/HL estructura
                if estructura and estructura != 'INDEFINIDO':
                    colores_est = {'ALCISTA_FUERTE': '#00ff00', 'ALCISTA': '#28a745', 'LATERAL': '#ffa500', 'BAJISTA': '#dc3545', 'BAJISTA_FUERTE': '#ff0000'}
                    color_est = colores_est.get(estructura, '#6c757d')
                    ruptura = hhhl_det.get('ruptura', '')
                    rup_text = f" ⚡{ruptura}" if ruptura else ""
                    indicadores_text.append(f"<span style='color:{color_est}'>📈{estructura}{rup_text}</span>")
                
                # Doble Suelo
                if doble_suelo:
                    indicadores_text.append(f"<span style='color:#00ff00'>🔄W DOBLE SUELO</span>")
                
                # Fibonacci Magnético P0/P1
                mag_info = item.get('p0p1_magnetico', {})
                if mag_info.get('p1_movido') or mag_info.get('p0_movido'):
                    reduccion = mag_info.get('rango_reducido_pct', 0)
                    fuerza_p1 = mag_info.get('p1_fuerza', 0)
                    fuerza_p0 = mag_info.get('p0_fuerza', 0)
                    indicadores_text.append(f"<span style='color:#9c27b0'>🧲MAG rango-{reduccion:.0f}%</span>")
                
                # Motivo de ajuste (solo si es real: BTC o FASE)
                if entrada_motivo and 'PATRON' not in str(entrada_motivo):
                    indicadores_text.append(f"<span style='color:#ff6600'>⚠️ {entrada_motivo}</span>")
                
                if indicadores_text:
                    st.markdown(f"<small>{' | '.join(indicadores_text)}</small>", unsafe_allow_html=True)

                cols_datos = st.columns([1.3, 1.3, 1.3, 1.3, 1.4, 1.4, 1.0])
                
                def mostrar_dato_grande(columna, titulo, precio, fecha=None, extra=None, color='black'):
                    with columna:
                        st.markdown(f"<small style='color:gray; font-size:0.7em; line-height:1;'>{titulo}</small>", unsafe_allow_html=True)
                        st.markdown(f"<b style='color:{color}; font-size:1.8em; line-height:1;'>{formatear_precio(precio)}</b>", unsafe_allow_html=True)
                        if fecha:
                            fecha_str = formatear_fecha_hora(fecha)
                            st.caption(f"📅 {fecha_str}")
                        if extra:
                            st.markdown(f"<small style='color:{color}; font-size:0.9em;'>{extra}</small>", unsafe_allow_html=True)

                mostrar_dato_grande(cols_datos[0], "Precio Actual", analysis.get('precio_actual', 0), estado.get('last_update', datetime.now()))

                # Para órdenes pendientes: usar valores_originales (los de cuando se creó la orden)
                # Para posiciones activas: usar datos del análisis actual
                valores_orig = item.get('valores_originales', {})
                
                if es_activa:
                    # Activas: usar analysis, con fallback a valores_originales (para posiciones SYNC/OCO)
                    p1_precio = (analysis.get('punto_1', {}).get('price', 0)
                                 or valores_orig.get('p1', 0)
                                 or item.get('p1_suelo', 0))
                    p1_fecha = item.get('p1_fecha', analysis.get('punto_1', {}).get('time'))
                    p0_precio = (analysis.get('punto_0', {}).get('price', 0)
                                 or valores_orig.get('p0', 0)
                                 or item.get('p0_maximo', 0))
                    p0_fecha = item.get('p0_fecha', analysis.get('punto_0', {}).get('time'))
                else:
                    # ORDEN PENDIENTE: mostrar valores ORIGINALES (no re-calculados)
                    p1_precio = valores_orig.get('p1', analysis.get('punto_1', {}).get('price', 0))
                    p1_fecha = valores_orig.get('p1_time', analysis.get('punto_1', {}).get('time'))
                    p0_precio = valores_orig.get('p0', analysis.get('punto_0', {}).get('price', 0))
                    p0_fecha = valores_orig.get('p0_time', analysis.get('punto_0', {}).get('time'))
                
                mostrar_dato_grande(cols_datos[1], "P1 Suelo", p1_precio, p1_fecha)
                mostrar_dato_grande(cols_datos[2], "P0 Máximo", p0_precio, p0_fecha)

                if es_activa:
                    precio_ent = item.get('precio_entrada_real', 0)
                    fecha_ent = item.get('fecha_entrada', None)
                else:
                    precio_ent = item.get('precio_entrada', 0)
                    fecha_ent = item.get('timestamp_creacion', None)
                label_compra = "Precio Compra" if es_activa else "Precio Entrada"
                # Calcular USDC invertidos y valor actual
                qty_trade = item.get('cantidad_comprada', item.get('cantidad', item.get('quantity', 0)))
                if not qty_trade:
                    qty_trade = item.get('binance_qty', 0)
                precio_actual_trade = analysis.get('precio_actual', precio_ent)
                if es_activa and qty_trade and precio_ent:
                    usdc_invertido = qty_trade * precio_ent
                    usdc_actual = qty_trade * precio_actual_trade if precio_actual_trade else 0
                    extra_compra = f"💵 {usdc_invertido:.2f} USDC invertidos"
                    if usdc_actual:
                        diff = usdc_actual - usdc_invertido
                        extra_compra += f"<br><small>Valor actual: {usdc_actual:.2f} USDC ({diff:+.2f})</small>"
                elif not es_activa:
                    usdc_config = config.get('importe_fijo_usdc', config.get('capital_fijo', 20.0))
                    extra_compra = f"💵 {usdc_config:.2f} USDC (configurado)"
                else:
                    extra_compra = None
                mostrar_dato_grande(cols_datos[3], label_compra, precio_ent, fecha_ent, extra=extra_compra)
                if es_activa and item.get('_oco_externa'):
                    cols_datos[3].caption("🔗 OCO activa en Binance")

                # TP y beneficio: usar originales para pendientes y OCO sync
                if es_activa:
                    # Para posiciones SYNC/OCO, análisis vacío → leer de valores_originales
                    precio_tp = (analysis.get('precio_tp', 0)
                                 or valores_orig.get('tp', 0)
                                 or valores_orig.get('precio_tp', 0))
                    benef_pct = (analysis.get('beneficio_esperado_pct', 0)
                                 or valores_orig.get('beneficio_pct', 0))
                else:
                    precio_tp = valores_orig.get('tp', analysis.get('precio_tp', 0))
                    benef_pct = valores_orig.get('beneficio_pct', analysis.get('beneficio_esperado_pct', 0))
                
                # Mostrar TP dinámico magnético si está activo
                tp_mag_info = item.get('tp_mag_info', {})
                if tp_mag_info and es_activa:
                    tp_ajustado = tp_mag_info.get('tp_ajustado', 0)
                    tipo_tp = tp_mag_info.get('tipo', '')
                    if tp_ajustado > 0 and precio_ent > 0:
                        benef_mag = ((tp_ajustado - precio_ent) / precio_ent) * 100
                        if tipo_tp == 'TP_EXTENDIDO':
                            mostrar_dato_grande(cols_datos[4], "Venta 🚀", tp_ajustado, extra=f"📈 +{benef_mag:.2f}%")
                        else:
                            mostrar_dato_grande(cols_datos[4], "Venta 🧲", tp_ajustado, extra=f"📈 +{benef_mag:.2f}%")
                    else:
                        mostrar_dato_grande(cols_datos[4], "Precio Venta", precio_tp, extra=f"📈 +{benef_pct:.2f}%")
                else:
                    mostrar_dato_grande(cols_datos[4], "Precio Venta", precio_tp, extra=f"📈 +{benef_pct:.2f}%")

                # SL: usar originales para pendientes
                if es_activa:
                    precio_sl = (analysis.get('precio_sl_definitivo', 0)
                                 or analysis.get('precio_sl_trigger', 0)
                                 or valores_orig.get('sl_definitivo', 0)
                                 or valores_orig.get('precio_sl_definitivo', 0))
                else:
                    precio_sl = valores_orig.get('sl_definitivo', analysis.get('precio_sl_definitivo', analysis.get('precio_sl_trigger', 0)))
                
                if precio_sl > 0 and precio_ent > 0:
                    perdida_pct = ((precio_sl - precio_ent) / precio_ent) * 100
                    mostrar_dato_grande(cols_datos[5], "Pérdidas (SL)", precio_sl, extra=f"📉 {perdida_pct:.2f}%", color='red')
                else:
                    mostrar_dato_grande(cols_datos[5], "Pérdidas (SL)", 0)

                with cols_datos[6]:
                    st.markdown("<small style='color:gray'>Fase</small>", unsafe_allow_html=True)
                    
                    if not es_activa:
                        st.markdown("**Esperando Entrada**", unsafe_allow_html=True)
                        if item.get('binance_order_id'):
                            st.caption(f"📤 Orden en Binance #{item['binance_order_id']}")
                        else:
                            st.caption("📋 Orden Enviada")
                    else:
                        precio_act = analysis.get('precio_actual', 0)
                        precio_ent_real = item.get('precio_entrada_real', 0)
                        if precio_ent_real > 0:
                            pnl_pct = ((precio_act - precio_ent_real) / precio_ent_real) * 100
                            
                            # Determinar fase y color
                            if abs(pnl_pct) < 0.01:  # Prácticamente 0%
                                color_text = "gray"
                                texto_fase = "Operando (Equilibrio)"
                            elif pnl_pct >= 0:
                                color_text = "green"
                                texto_fase = "Operando (Ganando)"
                            else:
                                color_text = "red"
                                texto_fase = "Operando (Perdiendo)"
                            
                            st.markdown(f"<b style='color:{color_text}; font-size:1.1em;'>{texto_fase}</b>", unsafe_allow_html=True)
                            st.caption(f"P&L: {pnl_pct:+.2f}%")
                        else:
                            st.markdown("**Operando**", unsafe_allow_html=True)

                detalles = item.get('detalles_score', {})
                desc_map = {
                    'proximidad': '¿Qué tan cerca está el precio actual del precio de entrada ideal?',
                    'momentum': '¿Cuánto ha subido la moneda en las últimas 24h?',
                    'volumen': 'Comparación del volumen de la moneda respecto a la más popular.',
                    'volatilidad': 'Cuánto se mueve el precio (el rango).',
                    'rsi': '📊 RSI: <30 sobrevendido (ideal compra), >70 sobrecomprado (evitar)',
                    'vol_confirm': '📊 Confirmación de volumen: >60 = volumen apoya el movimiento',
                    'ema_tend': '📊 Tendencia EMA: >60 = tendencia alcista, <40 = bajista',
                    'hhhl': '📈 Estructura HH/HL: 100=alcista fuerte, 50=lateral, 0=bajista fuerte',
                    'doble_suelo': '🔄 Doble Suelo: 100 = soporte confirmado por doble toque (W-pattern)'
                }
                
                with st.expander("🔍 Detalle del score"):
                    for key, desc in desc_map.items():
                        val = detalles.get(key, 0)
                        st.markdown(f"**{key.capitalize()}** {val}")
                        st.caption(desc)
                
                # ✏️ Edición manual de precios
                symbol_edit = item.get('symbol', 'X')
                with st.expander(f"✏️ Editar Precios"):
                    vals_orig_edit = item.get('valores_originales', {})
                    p0_actual = vals_orig_edit.get('p0', 0) or analysis.get('punto_0', {}).get('price', 0)
                    p1_actual = vals_orig_edit.get('p1', 0) or analysis.get('punto_1', {}).get('price', 0)
                    
                    # --- SECCION 1: Recalcular Fibonacci (P0/P1) ---
                    st.markdown("**📐 Recalcular Fibonacci** *(genera nuevos Entry, TP, SL)*")
                    col_p1, col_p0 = st.columns(2)
                    with col_p1:
                        nuevo_p1_edit = st.number_input(
                            "P1 (Suelo)", value=float(p1_actual) if p1_actual else 0.0,
                            format="%.8f", key=f"edit_p1_{symbol_edit}",
                            help="Punto más bajo del Fibonacci"
                        )
                    with col_p0:
                        nuevo_p0_edit = st.number_input(
                            "P0 (Máximo)", value=float(p0_actual) if p0_actual else 0.0,
                            format="%.8f", key=f"edit_p0_{symbol_edit}",
                            help="Punto más alto del Fibonacci"
                        )
                    
                    p0_cambio = abs(nuevo_p0_edit - p0_actual) > 1e-10 if p0_actual else nuevo_p0_edit > 0
                    p1_cambio = abs(nuevo_p1_edit - p1_actual) > 1e-10 if p1_actual else nuevo_p1_edit > 0
                    
                    if p0_cambio or p1_cambio:
                        # Preview de nuevos niveles
                        if nuevo_p0_edit > nuevo_p1_edit > 0:
                            r = nuevo_p0_edit - nuevo_p1_edit
                            entry_fib = config.get('entry_fib_level', 0.618) + config.get('entry_fib_ajuste', 0)
                            tp_fib = config.get('tp_fib_level', 0.382) + config.get('tp_fib_ajuste', 0)
                            prev_entry = nuevo_p1_edit + r * (1 - entry_fib)
                            prev_tp = nuevo_p1_edit + r * (1 - tp_fib)
                            st.caption(f"Preview: Entry {prev_entry:.6g} → TP {prev_tp:.6g} (+{((prev_tp-prev_entry)/prev_entry*100):.1f}%)")
                    
                    if st.button("📐 Recalcular Fibonacci", key=f"recalc_fib_{symbol_edit}"):
                        if p0_cambio or p1_cambio:
                            p0_val = nuevo_p0_edit if p0_cambio else None
                            p1_val = nuevo_p1_edit if p1_cambio else None
                            bot.editar_fibonacci(symbol_edit, nuevo_p0=p0_val, nuevo_p1=p1_val, es_activa=es_activa)
                            st.success(f"✅ Fibonacci recalculado")
                            st.rerun()
                        else:
                            st.info("Sin cambios en P0/P1")
                    
                    st.markdown("---")
                    
                    # --- SECCION 2: Ajustar precios individuales (NO toca Fibonacci) ---
                    st.markdown("**🎯 Ajustar precios** *(no modifica el Fibonacci)*")
                    
                    if es_activa:
                        # Posición activa: editar Entrada, TP y SL
                        entrada_actual_edit = item.get('precio_entrada_real', 0)
                        tp_actual_edit = vals_orig_edit.get('tp', analysis.get('precio_tp', 0))
                        sl_actual_edit = vals_orig_edit.get('sl_definitivo', analysis.get('precio_sl_definitivo', 0))
                        
                        col_ent_e, col_tp_e, col_sl_e = st.columns(3)
                        with col_ent_e:
                            nuevo_ent_edit = st.number_input(
                                "Entrada", value=float(entrada_actual_edit) if entrada_actual_edit else 0.0,
                                format="%.8f", key=f"edit_ent_{symbol_edit}",
                                help="Precio real de compra (para cálculo de beneficio)"
                            )
                        with col_tp_e:
                            nuevo_tp_edit = st.number_input(
                                "TP (Venta)", value=float(tp_actual_edit) if tp_actual_edit else 0.0,
                                format="%.8f", key=f"edit_tp_{symbol_edit}",
                                help="Precio al que quieres vender"
                            )
                        with col_sl_e:
                            nuevo_sl_edit = st.number_input(
                                "S.L.",
                                value=float(sl_actual_edit) if sl_actual_edit else 0.0,
                                format="%.8f", key=f"edit_sl_{symbol_edit}",
                                help="Precio de stop loss"
                            )
                        
                        if st.button("✅ Aplicar Cambios", key=f"aplicar_pos_{symbol_edit}"):
                            tp_cambio = nuevo_tp_edit if abs(nuevo_tp_edit - tp_actual_edit) > 1e-10 else None
                            sl_cambio = nuevo_sl_edit if abs(nuevo_sl_edit - sl_actual_edit) > 1e-10 else None
                            ent_cambio = abs(nuevo_ent_edit - entrada_actual_edit) > 1e-10 if entrada_actual_edit else False
                            
                            cambios = False
                            if tp_cambio or sl_cambio:
                                bot.editar_precios_posicion(symbol_edit, nuevo_tp=tp_cambio, nuevo_sl=sl_cambio)
                                cambios = True
                            if ent_cambio:
                                # Actualizar precio de entrada real (para cálculo P&L)
                                with bot._lock:
                                    pos = bot.open_positions.get(symbol_edit)
                                    if pos:
                                        pos['precio_entrada_real'] = nuevo_ent_edit
                                        bot.log(f"✏️ {symbol_edit} - Entrada editada → {fmt_precio(nuevo_ent_edit)}", "INFO")
                                cambios = True
                            
                            if cambios:
                                st.success(f"✅ Precios actualizados")
                                st.rerun()
                            else:
                                st.info("Sin cambios")
                    else:
                        # Orden pendiente: editar Entrada y TP
                        ent_actual_edit = item.get('precio_entrada', 0)
                        tp_actual_edit = vals_orig_edit.get('tp', analysis.get('precio_tp', 0))
                        
                        col_ent_e, col_tp_e = st.columns(2)
                        with col_ent_e:
                            nuevo_ent_edit = st.number_input(
                                "Precio Entrada",
                                value=float(ent_actual_edit) if ent_actual_edit else 0.0,
                                format="%.8f", key=f"edit_ent_{symbol_edit}",
                                help="Precio al que quieres comprar"
                            )
                        with col_tp_e:
                            nuevo_tp_edit = st.number_input(
                                "TP (Venta)",
                                value=float(tp_actual_edit) if tp_actual_edit else 0.0,
                                format="%.8f", key=f"edit_tp_{symbol_edit}",
                                help="Precio al que quieres vender"
                            )
                        
                        if st.button("✅ Aplicar Cambios", key=f"aplicar_ord_{symbol_edit}"):
                            ent_cambio = nuevo_ent_edit if abs(nuevo_ent_edit - ent_actual_edit) > 1e-10 else None
                            tp_cambio = nuevo_tp_edit if abs(nuevo_tp_edit - tp_actual_edit) > 1e-10 else None
                            if ent_cambio or tp_cambio:
                                bot.editar_precios_pendiente(symbol_edit, nuevo_entrada=ent_cambio, nuevo_tp=tp_cambio)
                                st.success(f"✅ Precios actualizados")
                                st.rerun()
                            else:
                                st.info("Sin cambios")

                st.markdown(close_div, unsafe_allow_html=True)
    
    # TAB 4: ESTADÍSTICAS
    with tab4:
        st.header("📈 Estadísticas de Trading")
        stats = estado['estadisticas']
        
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric("📊 Total", len(stats.get('operaciones_completadas', [])))
        with col2:
            st.metric("✅ Ganadoras", stats.get('operaciones_ganadoras', 0))
        with col3:
            st.metric("❌ Perdedoras", stats.get('operaciones_perdedoras', 0))
        with col4:
            total = len(stats.get('operaciones_completadas', []))
            winrate = (stats.get('operaciones_ganadoras', 0) / total * 100) if total > 0 else 0
            st.metric("🎯 Win Rate", f"{winrate:.1f}%")
        with col5:
            st.metric("💰 Beneficio", f"${stats.get('beneficio_total', 0):.2f}")
        
        st.markdown("---")
        
        # Botón reset visual
        col_hist, col_reset = st.columns([3, 1])
        with col_hist:
            st.subheader("📋 Historial de Operaciones")
        with col_reset:
            if st.button("🗑️ Limpiar Vista", help="Limpia el historial visual. El archivo estadisticas.json NO se borra."):
                bot.stats.reset_visual()
                st.rerun()
        
        operaciones = stats.get('operaciones_completadas', [])
        if operaciones:
            df_ops = pd.DataFrame(operaciones)
            if not df_ops.empty:
                # Función para formatear precio + fecha/hora
                def formatear_precio_fecha(precio, fecha):
                    if pd.isna(precio) or precio == 0:
                        return "N/A"
                    precio_fmt = formatear_precio(precio)
                    if pd.notna(fecha):
                        try:
                            if isinstance(fecha, str):
                                dt = datetime.fromisoformat(fecha)
                            else:
                                dt = fecha
                            fecha_fmt = dt.strftime("%m/%d %H:%M")
                            return f"{precio_fmt}\n{fecha_fmt}"
                        except:
                            return precio_fmt
                    return precio_fmt
                
                # Crear columnas formateadas
                if 'p1_suelo' in df_ops.columns:
                    fecha_p1_col = 'p1_fecha' if 'p1_fecha' in df_ops.columns else 'p1_time'
                    if fecha_p1_col in df_ops.columns:
                        df_ops['P1 Suelo'] = df_ops.apply(lambda row: formatear_precio_fecha(row['p1_suelo'], row[fecha_p1_col]), axis=1)
                    else:
                        df_ops['P1 Suelo'] = df_ops['p1_suelo'].apply(lambda x: formatear_precio(x) if pd.notna(x) else "N/A")
                
                if 'p0_maximo' in df_ops.columns:
                    fecha_p0_col = 'p0_fecha' if 'p0_fecha' in df_ops.columns else 'p0_time'
                    if fecha_p0_col in df_ops.columns:
                        df_ops['P0 Máximo'] = df_ops.apply(lambda row: formatear_precio_fecha(row['p0_maximo'], row[fecha_p0_col]), axis=1)
                    else:
                        df_ops['P0 Máximo'] = df_ops['p0_maximo'].apply(lambda x: formatear_precio(x) if pd.notna(x) else "N/A")
                
                # Entrada: precio_entrada + fecha_entrada
                precio_entrada_col = 'precio_entrada' if 'precio_entrada' in df_ops.columns else 'precio_entrada_real'
                if precio_entrada_col in df_ops.columns and 'fecha_entrada' in df_ops.columns:
                    df_ops['Entrada'] = df_ops.apply(lambda row: formatear_precio_fecha(row[precio_entrada_col], row['fecha_entrada']), axis=1)
                elif 'fecha_entrada' in df_ops.columns:
                    df_ops['Entrada'] = df_ops['fecha_entrada'].apply(lambda x: formatear_fecha_hora(x) if pd.notna(x) else "N/A")
                
                # Salida: precio_salida + fecha_salida
                precio_salida_col = 'precio_salida' if 'precio_salida' in df_ops.columns else 'precio_tp'
                if precio_salida_col in df_ops.columns and 'fecha_salida' in df_ops.columns:
                    df_ops['Salida'] = df_ops.apply(lambda row: formatear_precio_fecha(row[precio_salida_col], row['fecha_salida']), axis=1)
                elif 'fecha_salida' in df_ops.columns:
                    df_ops['Salida'] = df_ops['fecha_salida'].apply(lambda x: formatear_fecha_hora(x) if pd.notna(x) else "N/A")
                
                # Beneficio % con 1 decimal
                if 'beneficio_pct' in df_ops.columns:
                    df_ops['Beneficio %'] = df_ops['beneficio_pct'].apply(lambda x: f"{x:.1f}%" if pd.notna(x) else "N/A")
                
                # Beneficio $ con 1 decimal
                if 'beneficio_usd' in df_ops.columns:
                    df_ops['Beneficio $'] = df_ops['beneficio_usd'].apply(lambda x: f"${x:.1f}" if pd.notna(x) else "N/A")
                
                # Columna Temporalidad
                temporalidad_col = 'temporalidad' if 'temporalidad' in df_ops.columns else ('timeframe' if 'timeframe' in df_ops.columns else None)
                if temporalidad_col:
                    df_ops['Temporalidad'] = df_ops[temporalidad_col]
                else:
                    df_ops['Temporalidad'] = "N/A"
                
                # Moneda (symbol)
                if 'symbol' in df_ops.columns:
                    df_ops['Moneda'] = df_ops['symbol']
                
                # Modo (tipo)
                if 'tipo' in df_ops.columns:
                    df_ops['Modo'] = df_ops['tipo']
                
                # Seleccionar solo las columnas que queremos mostrar
                columnas_mostrar = []
                for col in ['Moneda', 'Temporalidad', 'P1 Suelo', 'P0 Máximo', 'Entrada', 'Salida', 'Beneficio %', 'Beneficio $', 'Modo']:
                    if col in df_ops.columns:
                        columnas_mostrar.append(col)
                
                # Añadir columna TradingView
                if 'symbol' in df_ops.columns:
                    tf_map_hist = {'1m': '1', '5m': '5', '15m': '15', '30m': '30', '1h': '60', '4h': '240', '1d': 'D', '1w': 'W'}
                    # Convertir timeframe a intervalo de VELAS (no temporalidad)
                    velas_hist_map = {'1h': '5m', '4h': '15m', '1d': '1h', '1w': '4h'}
                    def make_tv_link(row):
                        sym = row.get('symbol', '')
                        tf = row.get('timeframe', '1h')
                        vela = velas_hist_map.get(tf, tf)
                        tv_int = tf_map_hist.get(vela, '60')
                        return f"https://www.tradingview.com/chart/?symbol=BINANCE%3A{sym}&interval={tv_int}"
                    df_ops['📈 TV'] = df_ops.apply(make_tv_link, axis=1)
                    columnas_mostrar.append('📈 TV')
                
                df_ops_final = df_ops[columnas_mostrar]
                
                # Ordenar por fecha de entrada (si existe la columna original)
                if 'fecha_entrada' in df_ops.columns:
                    df_ops = df_ops.sort_values('fecha_entrada', ascending=False)
                    df_ops_final = df_ops[columnas_mostrar]
                
                # Colorear filas según ganancia/pérdida
                def colorear_fila(row):
                    if 'Beneficio %' in row.index and row['Beneficio %'] != "N/A":
                        try:
                            valor = float(row['Beneficio %'].replace('%', ''))
                            color = 'background-color: #58d68d; font-weight: bold; font-size: 16px' if valor >= 0 else 'background-color: #ec7063; font-weight: bold; font-size: 16px'
                            return [color] * len(row)
                        except:
                            pass
                    return [''] * len(row)
                
                df_styled = df_ops_final.style.apply(colorear_fila, axis=1)
                st.dataframe(
                    df_styled, 
                    use_container_width=True, 
                    hide_index=True, 
                    height=400,
                    column_config={
                        "📈 TV": st.column_config.LinkColumn(
                            "📈 TV",
                            display_text="Abrir",
                            help="Abrir en TradingView"
                        )
                    } if '📈 TV' in df_ops_final.columns else None
                )
        else:
            st.info("📭 No hay operaciones registradas")
                
                
                
    # TAB 5: LOGS
    with tab5:
        st.header("📜 Logs del Bot")
        
        logs = bot.get_logs()
        
        if not logs:
            st.info("📭 No hay logs recientes")
        else:
            # Botón para descargar logs
            col_logs1, col_logs2 = st.columns([3, 1])
            with col_logs2:
                logs_text = "\n".join([f"[{log['timestamp']}] [{log['nivel']}] {log['mensaje']}" for log in logs])
                st.download_button(
                    label="📥 Descargar Logs",
                    data=logs_text,
                    file_name=f"bot_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                    mime="text/plain",
                    help="Descarga todos los logs actuales en un archivo de texto."
                )
            
            for log in reversed(logs):
                color_class = {
                    'INFO': 'log-info',
                    'SUCCESS': 'log-success',
                    'WARNING': 'log-warning',
                    'ERROR': 'log-error'
                }.get(log['nivel'], 'log-info')
                
                mensaje = log['mensaje']
                
                # Detectar symbol y timeframe en el mensaje para enlace TradingView
                tv_link = ""
                # Buscar patrón: SIMBOLOUSDC seguido de | timeframe
                match_sym = re.search(r'(\w+USDC)\s*(?:\||[-–])', mensaje)
                match_tf = re.search(r'\|\s*(1m|5m|15m|30m|1h|4h|1d|1w)\s*\|', mensaje)
                if not match_tf:
                    # Buscar timeframe sin pipes (para compras/ventas)
                    match_tf = re.search(r'(1m|5m|15m|30m|1h|4h|1d|1w)', mensaje)
                
                if match_sym:
                    sym = match_sym.group(1)
                    tf_map_log = {'1m': '1', '5m': '5', '15m': '15', '30m': '30', '1h': '60', '4h': '240', '1d': 'D', '1w': 'W'}
                    # Convertir timeframe a intervalo de VELAS (no temporalidad)
                    velas_log_map = {'1h': '5m', '4h': '15m', '1d': '1h', '1w': '4h'}
                    tf_val = '5'  # default: 5m
                    if match_tf:
                        tf_detected = match_tf.group(1)
                        vela_log = velas_log_map.get(tf_detected, tf_detected)
                        tf_val = tf_map_log.get(vela_log, '60')
                    tv_url_log = f"https://www.tradingview.com/chart/?symbol=BINANCE%3A{sym}&interval={tf_val}"
                    tv_link = f" <a href='{tv_url_log}' target='_blank' style='text-decoration:none; font-size:0.8em;' title='Abrir {sym} en TradingView'>📈</a>"
                
                st.markdown(f"<span class='{color_class}'>[{log['timestamp']}] {mensaje}{tv_link}</span>", unsafe_allow_html=True)
  
    # ============================================
    # AUTO-REFRESH INTELIGENTE
    # ============================================
    st.markdown("---")
    
    col_refresh1, col_refresh2 = st.columns([3, 1])
    with col_refresh1:
        # Guardar intervalo en session_state para mantenerlo
        if 'intervalo_ui' not in st.session_state:
            st.session_state['intervalo_ui'] = 30
        intervalo_ui = st.slider(
            "⏱️ Actualizar UI cada (segundos)", 
            10, 300, 
            st.session_state['intervalo_ui'],
            key="slider_intervalo",
            help="Intervalo entre refrescos automáticos de la interfaz."
        )
        st.session_state['intervalo_ui'] = intervalo_ui
    with col_refresh2:
        if st.button("🔄 Actualizar Ahora"):
            st.rerun()
    
    # Auto-refresh si el bot está corriendo
    if bot.running:
        if 'last_rerun' not in st.session_state:
            st.session_state['last_rerun'] = time.time()
        
        tiempo_transcurrido = time.time() - st.session_state['last_rerun']
        
        if tiempo_transcurrido >= intervalo_ui:
            st.session_state['last_rerun'] = time.time()
            st.rerun()


if __name__ == "__main__":
    main()

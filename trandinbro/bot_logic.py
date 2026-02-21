# bot_logic.py - LÓGICA DEL BOT DE TRADING (Separada de la UI)
"""
Módulo que contiene toda la lógica del bot de trading.
Independiente de Streamlit para mejor rendimiento.
"""

import requests
import pandas as pd
import json
import time
import numpy as np
from datetime import datetime, timedelta
from functools import lru_cache
import threading
import queue

# ============================================
# HELPERS Y UTILIDADES
# ============================================

def now_utc():
    """Retorna datetime actual en UTC"""
    from datetime import timezone, timedelta
    return datetime.now(timezone(timedelta(hours=1))).replace(tzinfo=None)

def format_datetime_utc(dt):
    """Formatea datetime a string en UTC"""
    return dt.strftime("%Y-%m-%d %H:%M:%S UTC+1")

def fmt_precio(precio):
    """Formatea precio con decimales dinámicos según su magnitud"""
    if precio <= 0:
        return "0"
    elif precio < 0.00001:
        return f"{precio:.10f}"
    elif precio < 0.0001:
        return f"{precio:.9f}"
    elif precio < 0.001:
        return f"{precio:.8f}"
    elif precio < 0.01:
        return f"{precio:.7f}"
    elif precio < 0.1:
        return f"{precio:.6f}"
    elif precio < 1:
        return f"{precio:.5f}"
    elif precio < 10:
        return f"{precio:.4f}"
    elif precio < 100:
        return f"{precio:.3f}"
    else:
        return f"{precio:.2f}"

# ============================================
# CONFIGURACIÓN POR DEFECTO
# ============================================

def get_default_config():
    return {
        "pares_trading": ["USDC"],
        "modo_capital": "porcentaje",
        "capital_porcentaje": 10,
        "capital_fijo": 100,
        "balance_disponible": 10000,
        "modo_demo": True,
        "estrategia_scoring": "C",
        "entry_fib_level": 0.618,
        "tp_fib_level": 0.382,
        "modo_avanzado_activo": False,
        "reentry_fib_level": 0.786,
        "tp2_fib_level": 1.272,
        "safety_fib_level": 0.5,
        "sl_trigger_fib": 0.886,
        "sl_rebote_fib": 0.786,
        "sl_definitivo_fib": 0.95,
        "sl_timeout_candles": 5,
        "max_perdida_emergencia_pct": -15.0,
        "max_positions": 5,
        "monedas_excluidas": [],  # Lista de monedas a excluir del análisis (ej: ["BTCUSDC", "ETHUSDC"])
        "hold_coins": [],  # Monedas en HOLD manual (no tocar) (ej: ["BTC", "ETH"])
        "sync_interval_minutos": 10,  # Cada cuántos minutos sincronizar con Binance
        "swap_threshold": 20.0,
        "min_gain_pct": 1.0,
        "min_beneficio_pct": 0.5,
        "min_risk_reward": 1.0,  # Ratio mínimo Risk:Reward (1.0 = ganancia >= pérdida)
        "num_monedas_analizar": 50,
        "min_volumen_24h": 100000,  # Volumen mínimo en USDC (100k por defecto)
        "top_por_temporalidad": 20,
        "max_oportunidades_mostrar": 100,
        "lookback_p1": 50,
        "usar_multi_temporal": True,
        "temporalidades_activas": ["1h", "4h", "1d"],
        "config_temporalidades": {
            "1h": {"velas": "5m", "lookback": 300, "expectativa_horas": 2},
            "4h": {"velas": "15m", "lookback": 400, "expectativa_horas": 8},
            "1d": {"velas": "1h", "lookback": 200, "expectativa_horas": 48},
            "1w": {"velas": "4h", "lookback": 120, "expectativa_horas": 168}
        },
        "prioridad_temporal": ["1h", "4h", "1d", "1w"],
        "auto_refresh_interval": 30,
        "usar_deteccion_fase": True,
        "activar_reentrada_solo_subida": True,
        "usar_fib_magnetico": True,
        "tolerancia_magnetica": 0.02,
        "usar_magnetico_p0p1": True,  # Ajustar P0/P1 a soportes/resistencias reales
        "usar_magnetico_p1": True,  # Ajustar P1 independientemente
        "usar_magnetico_p0": True,  # Ajustar P0 independientemente
        "magnetico_p1_bidireccional": True,  # P1 puede subir Y bajar al soporte más fuerte
        "tolerancia_magnetica_p0p1": 0.30,  # 30% del rango P0-P1 (cuánto puede moverse)
        "usar_tp_dinamico": True,  # TP dinámico magnético durante posición abierta
        "lookback_soporte_historico": 300,  # Velas para buscar soportes históricos
        "min_fuerza_soporte_historico": 6,  # Mínimo de toques para considerar soporte
        "binance_api_key": "",
        "binance_api_secret": "",
        "telegram_bot_token": "",
        "telegram_chat_id": "",
        "config_bloqueada": False,
        "expandir_oportunidades": True,
        "proteccion_caida_btc": True,
        "umbral_caida_moderada": -3.0,
        "umbral_caida_fuerte": -5.0,
        "umbral_caida_severa": -7.0,
        "usar_blacklist_temporal": True,
        "blacklist_temporal_horas": 24,
        "no_reentrar_bajo_precio": True,
        "validar_p0_reciente": True,
        "max_velas_p0": 50,
        "min_caida_desde_p0": 0.05,
        "swap_automatico": False,
        "swap_min_score_diferencia": 15.0,
        "upgrade_ordenes_activo": True,
        "upgrade_min_score_diff": 10,
        "swap_min_ganancia_actual": 50.0,
        "swap_solo_si_cercano_entrada": True,
        "swap_distancia_maxima_entrada": 2.0,
        "min_score_compra": 60,
        "min_score_1h": 50,
        "min_score_4h": 50,
        "min_score_1d": 50,
        "min_score_1w": 50,
        # Filtrar monedas agotadas - CONFIGURACIÓN MEJORADA
        "filtrar_monedas_agotadas": True,
        "nivel_casi_compra": 0.65,        # Slider 1: Nivel cercano a compra (ej: 0.65 está cerca de 0.618)
        "nivel_rebote_agotado": 0.45,     # Slider 2: Nivel de rebote para considerar agotada (ej: 0.45 está cerca de 0.382)
        "entrada_btc_caida_activa": False,
        "entrada_btc_caida_ajuste": 0.0,
        "venta_btc_caida_activa": False,
        "venta_btc_caida_ajuste": 0.0,
        "usar_ordenes_limite": True,
        "tolerancia_orden_limite": 0.001,
        "timeout_orden_limite": 300,
        "cancelar_orden_si_p0_sube": True,
        "umbral_cancelacion_p0": 0.01,
        "reintentos_orden_limite": 3,
        "verificacion_orden_intervalo": 30,
        "cancelar_orden_rebote": False,
        "nivel_rebote_base": 0.382,
        "ajuste_rebote": 0.0,
        "criterio_ordenamiento": "score",  # "score" o "subida"
        # Protección por pérdidas
        "proteccion_perdidas_activa": True,
        "umbral_perdidas_pct": 75,
        "ventana_operaciones": 5,
        "proteccion_ops_para_volver": 1,  # Ops ganadoras en DEMO para volver a REAL
        # Notificaciones Telegram
        "telegram_notif_compras": True,
        "telegram_notif_ventas": True,
        "telegram_notif_ordenes": True,
        "telegram_notif_proteccion": True,
        "telegram_notif_btc_crash": True,
        "telegram_notif_upgrades": True,
        "telegram_notif_modo": True,
        "telegram_notif_errores": False,
        # Método P1
        "metodo_p1": "repetido",  # "repetido", "inflexion_low", "inflexion_close", "minimo_absoluto", "consenso"
        "confirmacion_ascenso_velas": 3,
        # Consenso P1
        "consenso_usar_repetido": True,
        "consenso_usar_inflexion_low": True,
        "consenso_usar_inflexion_close": False,
        "consenso_usar_minimo": True,
        "consenso_usar_soporte_historico": True,
        "consenso_tolerancia": 0.02,
        "consenso_override_recencia": True,  # Preferir mínimo reciente sobre mayoría
        "consenso_override_pct": 3.0,  # % mínimo de diferencia para override
        "consenso_estrategia": "minimo_validado",  # "mas_bajo", "minimo_validado" o "mayoria"
        # RSI y confirmación de tendencia
        "usar_filtro_rsi": True,
        "rsi_periodo": 14,
        "rsi_max_compra": 65,        # No comprar si RSI > 65 (sobrecomprado)
        "rsi_min_compra": 25,        # Ideal comprar si RSI < 25 (sobrevendido)
        "rsi_peso_score": 0.15,      # Peso del RSI en el scoring (15%)
        "usar_confirmacion_volumen": True,
        "volumen_ratio_minimo": 1.2, # Volumen actual debe ser 1.2x el promedio
        "volumen_peso_score": 0.10,  # Peso de confirmación volumen en score
        # EMA tendencia
        "usar_filtro_ema_tendencia": True,
        "ema_rapida": 8,
        "ema_lenta": 21,
        # Detección de patrón de recuperación (V-recovery)
        "usar_deteccion_patron": True,
        "patron_ajuste_automatico": True,  # Ajustar entry/TP según patrón
        "patron_min_beneficio_override": True,  # El patrón puede override min_beneficio
        # Niveles Fibonacci por patrón (configurables)
        "patron_fib_V_SHARP_entry": 0.382,
        "patron_fib_V_SHARP_tp": 0.0,
        "patron_fib_V_NORMAL_entry": 0.5,
        "patron_fib_V_NORMAL_tp": 0.236,
        "patron_fib_U_SHAPE_entry": 0.618,
        "patron_fib_U_SHAPE_tp": 0.382,
        "patron_fib_GRADUAL_entry": 0.618,
        "patron_fib_GRADUAL_tp": 0.382,
        "patron_fib_L_SHAPE_entry": 0.786,
        "patron_fib_L_SHAPE_tp": 0.5,
        # Estructura HH/HL
        "usar_filtro_hhhl": True,
        "hhhl_bloquear_bajista_fuerte": True,  # No comprar en BAJISTA_FUERTE
        "max_subida_24h_compra": 30.0,  # No comprar monedas que han subido más de X% en 24h
        "filtrar_lower_high": True,  # No comprar si P0 actual < máximo previo (lower high)
        # Escalones y Reentradas Progresivas
        "escalones_activo": True,
        "escalon_activacion": 0.5,
        "escalones_ajustes_personalizados": False,
        "escalon_trigger_base": 0.618,
        "escalon_trigger_ajuste": 0.005,
        "escalon_rebote_base": 0.5,
        "escalon_rebote_ajuste": 0.011,
        "escalon_definitivo_base": 0.618,
        "escalon_definitivo_ajuste": 0.005,
        "reentradas_progresivas": False,
        "tp_maximo_reentradas": -0.272,
    }

def save_config(config):
    try:
        with open('config.json', 'w') as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as e:
        print(f"Error guardando configuración: {e}")
        return False

def load_config():
    default_config = get_default_config().copy()
    try:
        with open('config.json', 'r') as f:
            user_config = json.load(f)
        needs_update = False
        for key, value in default_config.items():
            if key not in user_config:
                user_config[key] = value
                needs_update = True
        if needs_update:
            save_config(user_config)
        return user_config
    except FileNotFoundError:
        save_config(default_config)
        return default_config
    except Exception as e:
        print(f"Error cargando config: {e}")
        return default_config

# ============================================
# CONEXIONES API
# ============================================

def test_binance_connection(api_key, api_secret):
    try:
        import hmac, hashlib
        timestamp = int(time.time() * 1000)
        query_string = f"timestamp={timestamp}"
        signature = hmac.new(api_secret.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()
        headers = {'X-MBX-APIKEY': api_key}
        url = f"https://api.binance.com/api/v3/account?{query_string}&signature={signature}"
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            data = response.json()
            return {'success': True, 'message': '✅ Conexión exitosa con Binance API',
                    'balance_usdt': next((float(b['free']) for b in data.get('balances', []) if b['asset'] == 'USDT'), 0)}
        else:
            return {'success': False, 'message': f'❌ Error: {response.json().get("msg", "Desconocido")}'}
    except Exception as e:
        return {'success': False, 'message': f'❌ Error de conexión: {str(e)}'}

def test_telegram_connection(bot_token, chat_id):
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {'chat_id': chat_id, 'text': '🤖 Test TradingBro 1.0\n✅ Bot conectado!'}
        response = requests.post(url, json=payload, timeout=5)
        if response.status_code == 200:
            return {'success': True, 'message': '✅ Mensaje enviado a Telegram'}
        else:
            return {'success': False, 'message': f'❌ Error: {response.json().get("description", "Desconocido")}'}
    except Exception as e:
        return {'success': False, 'message': f'❌ Error de conexión: {str(e)}'}

def get_binance_balance(api_key, api_secret, asset='USDC'):
    """Obtiene el saldo disponible de un activo específico en Binance.
    Retorna float >= 0 si OK, None si hay error de conexión."""
    try:
        import hmac, hashlib
        timestamp = int(time.time() * 1000)
        query_string = f"timestamp={timestamp}"
        signature = hmac.new(api_secret.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()
        headers = {'X-MBX-APIKEY': api_key}
        url = f"https://api.binance.com/api/v3/account?{query_string}&signature={signature}"
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            data = response.json()
            balance = next((float(b['free']) for b in data.get('balances', []) if b['asset'] == asset), 0)
            return balance
        return None  # API error
    except Exception as e:
        return None  # Network error

def enviar_telegram(bot_token, chat_id, mensaje, config=None, tipo='general'):
    """Envía mensaje por Telegram. tipo: compra, venta, orden, proteccion, btc_crash, upgrade, modo, error, general"""
    if config:
        tipos_config = {
            'compra': 'telegram_notif_compras',
            'venta': 'telegram_notif_ventas',
            'orden': 'telegram_notif_ordenes',
            'proteccion': 'telegram_notif_proteccion',
            'btc_crash': 'telegram_notif_btc_crash',
            'upgrade': 'telegram_notif_upgrades',
            'modo': 'telegram_notif_modo',
            'error': 'telegram_notif_errores',
        }
        config_key = tipos_config.get(tipo)
        if config_key and not config.get(config_key, True):
            return  # Notificación desactivada por config
    
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        resp = requests.post(url, json={'chat_id': chat_id, 'text': mensaje, 'parse_mode': 'HTML'}, timeout=5)
        if resp.status_code != 200:
            print(f"Telegram error {resp.status_code}: {resp.text[:100]}")
    except Exception as e:
        print(f"Telegram send failed: {e}")

# ============================================
# ESTADÍSTICAS
# ============================================

class EstadisticasManager:
    def __init__(self):
        self.estadisticas = {
            'operaciones_completadas': [],
            'beneficio_total': 0,
            'operaciones_ganadoras': 0,
            'operaciones_perdedoras': 0,
            'swaps_realizados': 0
        }
        self.cargar()
    
    def cargar(self):
        try:
            with open('estadisticas.json', 'r') as f:
                self.estadisticas = json.load(f)
        except:
            pass
    
    def guardar(self):
        try:
            with open('estadisticas.json', 'w') as f:
                json.dump(self.estadisticas, f, indent=2)
            # Guardar también como CSV
            if self.estadisticas['operaciones_completadas']:
                df = pd.DataFrame(self.estadisticas['operaciones_completadas'])
                df.to_csv('historial_operaciones.csv', index=False)
        except:
            pass
    def reset_visual(self):
        """Resetea estadísticas solo en memoria (no el archivo)"""
        self.estadisticas = {
            'operaciones_completadas': [],
            'beneficio_total': 0,
            'operaciones_ganadoras': 0,
            'operaciones_perdedoras': 0,
            'swaps_realizados': 0
        }
    def registrar_operacion(self, symbol, fecha_entrada, fecha_salida, precio_entrada, precio_salida, beneficio_pct, beneficio_usd, tipo='DEMO', p1_suelo=0, p0_maximo=0, p1_fecha=None, p0_fecha=None, temporalidad='N/A'):
        """Registra una operación completada con TODOS los datos necesarios"""
        operacion = {
            'symbol': symbol,
            'temporalidad': temporalidad,
            'p1_suelo': p1_suelo,
            'p1_fecha': p1_fecha.isoformat() if hasattr(p1_fecha, 'isoformat') else p1_fecha,
            'p0_maximo': p0_maximo,
            'p0_fecha': p0_fecha.isoformat() if hasattr(p0_fecha, 'isoformat') else p0_fecha,
            'fecha_entrada': fecha_entrada,
            'fecha_salida': fecha_salida,
            'precio_entrada': precio_entrada,
            'precio_salida': precio_salida,
            'beneficio_pct': beneficio_pct,
            'beneficio_usd': beneficio_usd,
            'tipo': tipo,
            'timestamp': datetime.utcnow().isoformat()
        }
        self.estadisticas['operaciones_completadas'].append(operacion)
        self.estadisticas['beneficio_total'] += beneficio_usd
        if beneficio_pct > 0:
            self.estadisticas['operaciones_ganadoras'] += 1
        else:
            self.estadisticas['operaciones_perdedoras'] += 1
        self.guardar()

# ============================================
# BLACKLIST TEMPORAL
# ============================================

class BlacklistManager:
    def __init__(self):
        self.blacklist = {}
    
    def añadir(self, symbol, precio_entrada, config):
        if not config.get('usar_blacklist_temporal', True):
            return
        self.blacklist[symbol] = {
            'timestamp': datetime.utcnow(),
            'precio_entrada_perdedor': precio_entrada,
            'bloqueado_hasta': datetime.utcnow() + timedelta(hours=config.get('blacklist_temporal_horas', 24))
        }
    
    def verificar(self, symbol, precio_actual, config):
        if not config.get('usar_blacklist_temporal', True):
            return False
        if symbol not in self.blacklist:
            return False
        info = self.blacklist[symbol]
        if datetime.utcnow() >= info['bloqueado_hasta']:
            del self.blacklist[symbol]
            return False
        if config.get('no_reentrar_bajo_precio', True):
            if precio_actual <= info['precio_entrada_perdedor'] * 1.02:
                return True
        return True

# ============================================
# DATOS DE MERCADO
# ============================================

class MarketDataManager:
    def __init__(self):
        self._cache = {}
        self._cache_time = {}
        self._trading_pairs = set()  # Pares activos para trading
        self._last_exchange_info = None
        self._symbol_filters = {}  # Filtros por símbolo (lot_size, tick_size, min_notional)
    
    def _actualizar_pares_activos(self, pair_suffix='USDC'):
        """Obtiene la lista de pares que están activos para trading y sus filtros"""
        cache_key = f"exchange_info_{pair_suffix}"
        # Actualizar cada 10 minutos
        if cache_key in self._cache:
            if (datetime.now() - self._cache_time.get(cache_key, datetime.min)).seconds < 600:
                return
        try:
            response = requests.get('https://api.binance.com/api/v3/exchangeInfo', timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # Filtrar solo pares activos (status = TRADING)
            self._trading_pairs = set()
            for symbol_info in data.get('symbols', []):
                if (symbol_info.get('status') == 'TRADING' and 
                    symbol_info.get('symbol', '').endswith(pair_suffix)):
                    sym = symbol_info['symbol']
                    self._trading_pairs.add(sym)
                    
                    # Parsear filtros para órdenes reales
                    filters = {}
                    for f in symbol_info.get('filters', []):
                        if f['filterType'] == 'LOT_SIZE':
                            filters['step_size'] = float(f['stepSize'])
                            filters['min_qty'] = float(f['minQty'])
                            filters['max_qty'] = float(f['maxQty'])
                        elif f['filterType'] == 'PRICE_FILTER':
                            filters['tick_size'] = float(f['tickSize'])
                            filters['min_price'] = float(f['minPrice'])
                        elif f['filterType'] == 'NOTIONAL':
                            filters['min_notional'] = float(f.get('minNotional', 0))
                        elif f['filterType'] == 'MIN_NOTIONAL':
                            filters['min_notional'] = float(f.get('minNotional', 0))
                    self._symbol_filters[sym] = filters
            
            self._cache[cache_key] = True
            self._cache_time[cache_key] = datetime.now()
        except Exception as e:
            print(f"Error actualizando pares activos: {e}")
    
    def get_top_volume_pairs(self, pair_suffix='USDC', limit=100, min_volume=0):
        # Primero actualizar lista de pares activos
        self._actualizar_pares_activos(pair_suffix)
        
        cache_key = f"top_{pair_suffix}_{limit}_{min_volume}"
        if cache_key in self._cache:
            if (datetime.now() - self._cache_time.get(cache_key, datetime.min)).seconds < 120:
                return self._cache[cache_key]
        try:
            response = requests.get('https://api.binance.com/api/v3/ticker/24hr', timeout=10)
            response.raise_for_status()
            df = pd.DataFrame(response.json())
            df_filtered = df[df['symbol'].str.endswith(pair_suffix)].copy()
            
            # Filtrar solo pares activos para trading
            if self._trading_pairs:
                df_filtered = df_filtered[df_filtered['symbol'].isin(self._trading_pairs)]
            
            for col in ['quoteVolume', 'priceChangePercent', 'lastPrice', 'volume']:
                df_filtered[col] = pd.to_numeric(df_filtered[col], errors='coerce')
            
            # Filtrar por volumen mínimo (en USDC)
            if min_volume > 0:
                df_filtered = df_filtered[df_filtered['quoteVolume'] >= min_volume]
            
            result = df_filtered.sort_values('quoteVolume', ascending=False).head(limit)
            self._cache[cache_key] = result
            self._cache_time[cache_key] = datetime.now()
            return result
        except:
            return pd.DataFrame()
    
    def get_klines_data(self, symbol, interval, limit=200):
        cache_key = f"klines_{symbol}_{interval}_{limit}"
        # Cache TTL dinámico: velas cortas = cache corto, velas largas = cache largo
        cache_ttl = {'1m': 30, '5m': 60, '15m': 120, '30m': 180, '1h': 300, '4h': 600, '1d': 900}.get(interval, 90)
        if cache_key in self._cache:
            if (datetime.now() - self._cache_time.get(cache_key, datetime.min)).seconds < cache_ttl:
                return self._cache[cache_key]
        try:
            params = {'symbol': symbol, 'interval': interval, 'limit': limit}
            response = requests.get("https://api.binance.com/api/v3/klines", params=params, timeout=5)
            response.raise_for_status()
            df = pd.DataFrame(response.json())
            df.columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time',
                          'quote_volume', 'trades', 'taker_buy_base', 'taker_buy_quote', 'ignore']
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            self._cache[cache_key] = df
            self._cache_time[cache_key] = datetime.now()
            return df
        except:
            return pd.DataFrame()
    
    def get_current_price(self, symbol):
        try:
            response = requests.get(f'https://api.binance.com/api/v3/ticker/price?symbol={symbol}', timeout=5)
            data = response.json()
            return float(data['price'])
        except:
            return 0
    
    def get_24h_ticker(self, symbol):
        """Obtiene datos de 24h para un symbol específico.
        Retorna dict con priceChangePercent, volume, etc. o None."""
        cache_key = f"ticker24h_{symbol}"
        if cache_key in self._cache:
            if (datetime.now() - self._cache_time.get(cache_key, datetime.min)).seconds < 120:
                return self._cache[cache_key]
        try:
            response = requests.get(
                f'https://api.binance.com/api/v3/ticker/24hr?symbol={symbol}', timeout=5)
            if response.status_code == 200:
                data = response.json()
                self._cache[cache_key] = data
                self._cache_time[cache_key] = datetime.now()
                return data
            return None
        except:
            return None
    
    def clear_cache(self):
        self._cache = {}
        self._cache_time = {}
    
    def get_symbol_filters(self, symbol):
        """Devuelve los filtros de un símbolo (tick_size, step_size, min_notional)"""
        if symbol not in self._symbol_filters:
            # Forzar actualización
            suffix = 'USDC' if symbol.endswith('USDC') else 'USDT'
            self._cache.pop(f"exchange_info_{suffix}", None)
            self._actualizar_pares_activos(suffix)
        return self._symbol_filters.get(symbol, {})

# ============================================
# GESTIÓN DE ÓRDENES BINANCE (REAL)
# ============================================

class BinanceOrderManager:
    """Gestiona órdenes reales en Binance: LIMIT BUY, OCO SELL, cancelaciones."""
    
    def __init__(self, market: MarketDataManager):
        self.market = market
        self._api_key = ''
        self._api_secret = ''
    
    def configurar(self, api_key, api_secret):
        """Configura las claves API"""
        self._api_key = api_key
        self._api_secret = api_secret
    
    def _is_configured(self):
        return bool(self._api_key and self._api_secret)
    
    def _sign_request(self, params):
        """Firma una petición con HMAC-SHA256"""
        import hmac, hashlib
        params['timestamp'] = int(time.time() * 1000)
        query_string = '&'.join(f"{k}={v}" for k, v in params.items())
        signature = hmac.new(
            self._api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return query_string + f"&signature={signature}"
    
    def _headers(self):
        return {'X-MBX-APIKEY': self._api_key}
    
    def _get_precision(self, value):
        """Calcula decimales de un valor evitando notación científica de Python"""
        if value <= 0:
            return 8
        # Usar f-string para evitar '1e-08' → '0.00000001'
        s = f"{value:.20f}".rstrip('0')
        if '.' in s:
            return len(s.split('.')[1])
        return 0
    
    def _adjust_price(self, price, symbol):
        """Ajusta precio al tick_size del símbolo"""
        filters = self.market.get_symbol_filters(symbol)
        tick_size = filters.get('tick_size', 0.00000001)
        if tick_size > 0:
            precision = self._get_precision(tick_size)
            return round(price - (price % tick_size), precision)
        return price
    
    def _adjust_quantity(self, quantity, symbol):
        """Ajusta cantidad al step_size del símbolo"""
        filters = self.market.get_symbol_filters(symbol)
        step_size = filters.get('step_size', 0.00000001)
        min_qty = filters.get('min_qty', 0)
        if step_size > 0:
            precision = self._get_precision(step_size)
            qty = round(quantity - (quantity % step_size), precision)
            return max(qty, min_qty)
        return quantity
    
    def _format_number(self, value, max_decimals=10):
        """Formatea número para Binance API: sin notación científica, sin trailing zeros"""
        s = f"{value:.{max_decimals}f}".rstrip('0').rstrip('.')
        return s if s else '0'
    
    def place_limit_buy(self, symbol, price, usdc_amount):
        """Coloca orden LIMIT BUY. Retorna dict con orderId o None si falla."""
        if not self._is_configured():
            return {'error': 'API no configurada'}
        
        adj_price = self._adjust_price(price, symbol)
        quantity = usdc_amount / adj_price
        adj_qty = self._adjust_quantity(quantity, symbol)
        
        # Verificar mín notional
        filters = self.market.get_symbol_filters(symbol)
        min_notional = filters.get('min_notional', 5.0)
        if adj_price * adj_qty < min_notional:
            return {'error': f'Notional {adj_price * adj_qty:.2f} < min {min_notional}'}
        
        params = {
            'symbol': symbol,
            'side': 'BUY',
            'type': 'LIMIT',
            'timeInForce': 'GTC',
            'price': self._format_number(adj_price),
            'quantity': self._format_number(adj_qty),
        }
        
        try:
            signed = self._sign_request(params)
            url = f"https://api.binance.com/api/v3/order?{signed}"
            response = requests.post(url, headers=self._headers(), timeout=10)
            data = response.json()
            
            if response.status_code == 200:
                return {
                    'success': True,
                    'orderId': data['orderId'],
                    'price': float(data.get('price', adj_price)),
                    'quantity': float(data.get('origQty', adj_qty)),
                    'status': data.get('status', 'NEW')
                }
            else:
                return {'error': data.get('msg', f'HTTP {response.status_code}')}
        except Exception as e:
            return {'error': str(e)}
    
    def place_oco_sell(self, symbol, quantity, tp_price, sl_trigger_price, sl_limit_price):
        """Coloca OCO SELL (TP arriba + SL abajo). Usa nueva API Binance con aboveType/belowType.
        
        IMPORTANTE: La OCO es solo la RED DE SEGURIDAD final.
        El bot maneja internamente trigger → rebote → definitivo.
        La OCO de Binance solo usa sl_definitivo con gap mínimo para garantizar ejecución."""
        if not self._is_configured():
            return {'error': 'API no configurada'}
        
        adj_tp = self._adjust_price(tp_price, symbol)
        adj_sl_limit = self._adjust_price(sl_limit_price, symbol)  # sl_definitivo
        adj_qty = self._adjust_quantity(quantity, symbol)
        
        # El trigger de Binance debe estar justo encima del limit (0.2% gap)
        # para garantizar que se ejecute cuando llegue al nivel definitivo
        sl_trigger_real = adj_sl_limit * 1.002
        adj_sl_trigger = self._adjust_price(sl_trigger_real, symbol)
        
        # Asegurar que trigger >= limit
        if adj_sl_trigger <= adj_sl_limit:
            adj_sl_trigger = adj_sl_limit
        
        # Nueva API Binance OCO:
        # above = Take Profit (precio sube → LIMIT_MAKER)
        # below = Stop Loss (precio baja → STOP_LOSS_LIMIT)
        params = {
            'symbol': symbol,
            'side': 'SELL',
            'quantity': self._format_number(adj_qty),
            'aboveType': 'LIMIT_MAKER',
            'abovePrice': self._format_number(adj_tp),
            'belowType': 'STOP_LOSS_LIMIT',
            'belowPrice': self._format_number(adj_sl_limit),
            'belowStopPrice': self._format_number(adj_sl_trigger),
            'belowTimeInForce': 'GTC',
        }
        
        try:
            signed = self._sign_request(params)
            url = f"https://api.binance.com/api/v3/orderList/oco?{signed}"
            response = requests.post(url, headers=self._headers(), timeout=10)
            data = response.json()
            
            if response.status_code == 200:
                return {
                    'success': True,
                    'orderListId': data.get('orderListId'),
                    'orders': data.get('orderReports', []),
                    'tp_price': adj_tp,
                    'sl_trigger': adj_sl_trigger,
                    'sl_limit': adj_sl_limit
                }
            else:
                return {'error': data.get('msg', f'HTTP {response.status_code}')}
        except Exception as e:
            return {'error': str(e)}
    
    def cancel_order(self, symbol, order_id):
        """Cancela una orden por orderId"""
        if not self._is_configured():
            return {'error': 'API no configurada'}
        params = {'symbol': symbol, 'orderId': order_id}
        try:
            signed = self._sign_request(params)
            url = f"https://api.binance.com/api/v3/order?{signed}"
            response = requests.delete(url, headers=self._headers(), timeout=10)
            return response.json()
        except Exception as e:
            return {'error': str(e)}
    
    def cancel_oco(self, symbol, order_list_id):
        """Cancela un OCO por orderListId"""
        if not self._is_configured():
            return {'error': 'API no configurada'}
        params = {'symbol': symbol, 'orderListId': order_list_id}
        try:
            signed = self._sign_request(params)
            url = f"https://api.binance.com/api/v3/orderList?{signed}"
            response = requests.delete(url, headers=self._headers(), timeout=10)
            return response.json()
        except Exception as e:
            return {'error': str(e)}
    
    def place_market_sell(self, symbol, quantity):
        """Venta a mercado (emergencia o cierre manual)"""
        if not self._is_configured():
            return {'error': 'API no configurada'}
        adj_qty = self._adjust_quantity(quantity, symbol)
        params = {
            'symbol': symbol,
            'side': 'SELL',
            'type': 'MARKET',
            'quantity': self._format_number(adj_qty),
        }
        try:
            signed = self._sign_request(params)
            url = f"https://api.binance.com/api/v3/order?{signed}"
            response = requests.post(url, headers=self._headers(), timeout=10)
            data = response.json()
            if response.status_code == 200:
                # Calcular precio medio de ejecución
                fills = data.get('fills', [])
                if fills:
                    total_qty = sum(float(f['qty']) for f in fills)
                    total_cost = sum(float(f['qty']) * float(f['price']) for f in fills)
                    avg_price = total_cost / total_qty if total_qty > 0 else 0
                else:
                    avg_price = 0
                return {'success': True, 'orderId': data['orderId'], 'avg_price': avg_price}
            else:
                return {'error': data.get('msg', f'HTTP {response.status_code}')}
        except Exception as e:
            return {'error': str(e)}
    
    def get_order_status(self, symbol, order_id):
        """Consulta estado de una orden"""
        if not self._is_configured():
            return None
        params = {'symbol': symbol, 'orderId': order_id}
        try:
            signed = self._sign_request(params)
            url = f"https://api.binance.com/api/v3/order?{signed}"
            response = requests.get(url, headers=self._headers(), timeout=5)
            if response.status_code == 200:
                return response.json()
        except:
            pass
        return None
    
    def get_oco_status(self, symbol, order_list_id):
        """Consulta estado de una OCO"""
        if not self._is_configured():
            return None
        params = {'orderListId': order_list_id}
        try:
            signed = self._sign_request(params)
            url = f"https://api.binance.com/api/v3/orderList?{signed}"
            response = requests.get(url, headers=self._headers(), timeout=5)
            if response.status_code == 200:
                return response.json()
        except:
            pass
        return None
    
    def get_order_status(self, symbol, order_id):
        """Consulta estado de una orden individual"""
        if not self._is_configured():
            return None
        params = {'symbol': symbol, 'orderId': order_id}
        try:
            signed = self._sign_request(params)
            url = f"https://api.binance.com/api/v3/order?{signed}"
            response = requests.get(url, headers=self._headers(), timeout=5)
            if response.status_code == 200:
                return response.json()
        except:
            pass
        return None

    def get_open_orders(self, symbol=None):
        """Obtiene todas las órdenes abiertas en Binance. Sin symbol = todas las monedas."""
        if not self._is_configured():
            return None
        params = {}
        if symbol:
            params['symbol'] = symbol
        try:
            signed = self._sign_request(params)
            url = f"https://api.binance.com/api/v3/openOrders?{signed}"
            response = requests.get(url, headers=self._headers(), timeout=10)
            if response.status_code == 200:
                return response.json()
            return None
        except:
            return None
    
    def get_all_balances(self, min_value_usdc=3.0):
        """Obtiene todos los balances del account con valor > min_value_usdc.
        Retorna dict {asset: {'free': float, 'locked': float, 'total': float}} o None si error."""
        if not self._is_configured():
            return None
        try:
            import hmac, hashlib
            params = {'timestamp': int(time.time() * 1000)}
            query_string = '&'.join(f"{k}={v}" for k, v in params.items())
            signature = hmac.new(
                self._api_secret.encode('utf-8'),
                query_string.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            url = f"https://api.binance.com/api/v3/account?{query_string}&signature={signature}"
            response = requests.get(url, headers=self._headers(), timeout=10)
            if response.status_code != 200:
                return None
            
            data = response.json()
            balances = {}
            for b in data.get('balances', []):
                free = float(b['free'])
                locked = float(b['locked'])
                total = free + locked
                if total > 0:
                    asset = b['asset']
                    # Ignorar stablecoins
                    if asset in ('USDC', 'USDT', 'BUSD', 'EUR', 'USD', 'FDUSD'):
                        continue
                    balances[asset] = {'free': free, 'locked': locked, 'total': total}
            return balances
        except:
            return None

    def get_my_trades(self, symbol, limit=5):
        """Obtiene los últimos trades ejecutados de un symbol.
        Retorna lista de trades o None si error."""
        if not self._is_configured():
            return None
        try:
            params = {'symbol': symbol, 'limit': limit}
            signed = self._sign_request(params)
            url = f"https://api.binance.com/api/v3/myTrades?{signed}"
            response = requests.get(url, headers=self._headers(), timeout=10)
            if response.status_code == 200:
                return response.json()
            return None
        except:
            return None

    def get_last_buy_price(self, symbol):
        """Obtiene precio real de la última compra de un symbol.
        Retorna (precio, cantidad, fecha_ms) o (None, None, None)."""
        trades = self.get_my_trades(symbol, limit=10)
        if not trades:
            return None, None, None
        # Buscar última compra (isBuyer=True)
        for trade in reversed(trades):
            if trade.get('isBuyer', False):
                price = float(trade['price'])
                qty = float(trade['qty'])
                ts = trade.get('time', 0)
                return price, qty, ts
        return None, None, None

class TechnicalAnalyzer:
    def __init__(self, market_data: MarketDataManager):
        self.market = market_data
    
    def detectar_fase_mercado(self):
        try:
            df = self.market.get_klines_data('BTCUSDC', '1h', 100)
            if df.empty:
                return 'DESCONOCIDO'
            df['ema20'] = df['close'].ewm(span=20, adjust=False).mean()
            df['ema50'] = df['close'].ewm(span=50, adjust=False).mean()
            precio_actual = df['close'].iloc[-1]
            ema20_actual = df['ema20'].iloc[-1]
            ema50_actual = df['ema50'].iloc[-1]
            if precio_actual > ema20_actual > ema50_actual:
                return 'SUBIDA'
            elif precio_actual < ema20_actual < ema50_actual:
                return 'BAJADA'
            else:
                return 'LATERAL'
        except:
            return 'DESCONOCIDO'
    
    def detectar_caida_btc(self):
        try:
            df_btc = self.market.get_klines_data('BTCUSDC', '1h', 24)
            if df_btc.empty or len(df_btc) < 2:
                return {'status': 'OK', 'caida_1h': 0, 'caida_4h': 0, 'caida_24h': 0, 'nivel_alerta': 'NORMAL'}
            precio_actual = df_btc['close'].iloc[-1]
            caida_1h = ((precio_actual - df_btc['close'].iloc[-2]) / df_btc['close'].iloc[-2]) * 100
            caida_4h = ((precio_actual - df_btc['close'].iloc[-5]) / df_btc['close'].iloc[-5]) * 100 if len(df_btc) >= 5 else caida_1h
            caida_24h = ((precio_actual - df_btc['close'].iloc[0]) / df_btc['close'].iloc[0]) * 100
            if caida_1h <= -7 or caida_4h <= -10 or caida_24h <= -15:
                nivel = 'SEVERA'
            elif caida_1h <= -5 or caida_4h <= -7 or caida_24h <= -10:
                nivel = 'FUERTE'
            elif caida_1h <= -3 or caida_4h <= -5 or caida_24h <= -7:
                nivel = 'MODERADA'
            else:
                nivel = 'NORMAL'
            return {'status': 'OK', 'caida_1h': round(caida_1h, 2), 'caida_4h': round(caida_4h, 2),
                    'caida_24h': round(caida_24h, 2), 'nivel_alerta': nivel, 'precio_actual_btc': precio_actual}
        except:
            return {'status': 'ERROR', 'nivel_alerta': 'NORMAL'}
    
    def encontrar_niveles_clave(self, df_klines, lookback=100):
        """Encuentra niveles de soporte/resistencia clave usando clústering de precios"""
        if df_klines.empty or len(df_klines) < 20:
            return [], []
        df_recent = df_klines.tail(min(lookback, len(df_klines))).reset_index(drop=True)
        
        # === MÉTODO 1: Pivotes locales (swing highs/lows) ===
        ventana = 5
        soportes_pivot = []
        resistencias_pivot = []
        for i in range(ventana, len(df_recent) - ventana):
            # Soporte: mínimo local
            if df_recent['low'].iloc[i] == df_recent['low'].iloc[i-ventana:i+ventana+1].min():
                soportes_pivot.append(float(df_recent['low'].iloc[i]))
            # Resistencia: máximo local
            if df_recent['high'].iloc[i] == df_recent['high'].iloc[i-ventana:i+ventana+1].max():
                resistencias_pivot.append(float(df_recent['high'].iloc[i]))
        
        # === MÉTODO 2: Zonas de congestión (muchos cierres en el mismo nivel) ===
        all_closes = df_recent['close'].values
        all_highs = df_recent['high'].values
        all_lows = df_recent['low'].values
        
        # Crear bins del 0.5% del rango total
        precio_min = min(all_lows)
        precio_max = max(all_highs)
        if precio_max <= precio_min:
            return soportes_pivot, resistencias_pivot
        
        n_bins = 50
        bin_size = (precio_max - precio_min) / n_bins
        if bin_size <= 0:
            return soportes_pivot, resistencias_pivot
        
        # Contar toques en cada zona
        zonas = {}
        for precio_array in [all_closes, all_highs, all_lows]:
            for precio in precio_array:
                bin_idx = int((float(precio) - precio_min) / bin_size)
                bin_idx = min(bin_idx, n_bins - 1)
                zona_precio = precio_min + (bin_idx + 0.5) * bin_size
                zonas[zona_precio] = zonas.get(zona_precio, 0) + 1
        
        # Las zonas con más toques son S/R fuertes (>= 4 toques)
        umbral_toques = max(4, len(df_recent) * 0.05)  # Al menos 5% de las velas
        zonas_fuertes = sorted(
            [(precio, toques) for precio, toques in zonas.items() if toques >= umbral_toques],
            key=lambda x: x[1], reverse=True
        )[:20]  # Top 20 zonas
        
        # Añadir zonas de congestión a soportes/resistencias
        soportes_congestion = [z[0] for z in zonas_fuertes]
        
        # Combinar y deduplicar (merge niveles dentro del 1%)
        todos_soportes = soportes_pivot + soportes_congestion
        todas_resistencias = resistencias_pivot + soportes_congestion  # Las zonas fuertes son S y R
        
        soportes = self._deduplicar_niveles(todos_soportes, tolerancia_pct=1.0)
        resistencias = self._deduplicar_niveles(todas_resistencias, tolerancia_pct=1.0)
        
        return soportes, resistencias
    
    def _deduplicar_niveles(self, niveles, tolerancia_pct=1.0):
        """Agrupa niveles cercanos y devuelve el promedio de cada grupo"""
        if not niveles:
            return []
        niveles_sorted = sorted(niveles)
        grupos = [[niveles_sorted[0]]]
        
        for nivel in niveles_sorted[1:]:
            if abs(nivel - grupos[-1][-1]) / grupos[-1][-1] * 100 <= tolerancia_pct:
                grupos[-1].append(nivel)
            else:
                grupos.append([nivel])
        
        # Retornar promedio de cada grupo, ponderado por frecuencia
        return [sum(g) / len(g) for g in grupos]
    
    def ajustar_p0_p1_magnetico(self, price_p1, max_dinamico_p0, df_klines, config):
        """
        AJUSTE MAGNÉTICO DE P0 Y P1:
        Mueve P1 y P0 a los soportes/resistencias más FUERTES (más tocados por velas).
        
        Clave: La tolerancia se mide como % del RANGO (P0-P1), no del precio.
        
        Configuración:
        - usar_magnetico_p1: Activa/desactiva ajuste de P1 (independiente)
        - usar_magnetico_p0: Activa/desactiva ajuste de P0 (independiente)
        - magnetico_p1_bidireccional: Si True, P1 puede subir Y bajar al soporte más fuerte
          Si False, P1 solo sube (comportamiento anterior)
        """
        rango = max_dinamico_p0 - price_p1
        if rango <= 0:
            return price_p1, max_dinamico_p0, False, {}
        
        tolerancia_rango = config.get('tolerancia_magnetica_p0p1', 0.30)
        max_movimiento = rango * tolerancia_rango
        
        # Obtener S/R con fuerza (número de toques)
        soportes_con_fuerza, resistencias_con_fuerza = self._encontrar_niveles_con_fuerza(df_klines, lookback=150)
        
        p1_ajustado = price_p1
        mejor_fuerza_p1 = 0
        p0_ajustado = max_dinamico_p0
        mejor_fuerza_p0 = 0
        
        # --- Ajustar P1 al SOPORTE MÁS FUERTE ---
        if config.get('usar_magnetico_p1', True):
            bidireccional = config.get('magnetico_p1_bidireccional', True)
            
            for soporte, fuerza in soportes_con_fuerza:
                if bidireccional:
                    # P1 puede ir ARRIBA o ABAJO dentro del rango permitido
                    distancia = abs(soporte - price_p1)
                    if distancia <= max_movimiento and fuerza > mejor_fuerza_p1:
                        p1_ajustado = soporte
                        mejor_fuerza_p1 = fuerza
                else:
                    # P1 solo sube (comportamiento original)
                    if price_p1 <= soporte <= (price_p1 + max_movimiento):
                        if fuerza > mejor_fuerza_p1:
                            p1_ajustado = soporte
                            mejor_fuerza_p1 = fuerza
        
        # --- Ajustar P0 a la RESISTENCIA MÁS FUERTE (solo si activado) ---
        if config.get('usar_magnetico_p0', True):
            for resistencia, fuerza in resistencias_con_fuerza:
                # P0 solo baja (no ampliar rango innecesariamente)
                if (max_dinamico_p0 - max_movimiento) <= resistencia <= max_dinamico_p0:
                    if fuerza > mejor_fuerza_p0:
                        p0_ajustado = resistencia
                        mejor_fuerza_p0 = fuerza
        
        # Validar que el rango ajustado sigue siendo positivo y razonable
        rango_ajustado = p0_ajustado - p1_ajustado
        if rango_ajustado <= 0 or rango_ajustado < rango * 0.2:
            return price_p1, max_dinamico_p0, False, {}
        
        # Calcular dirección del movimiento de P1
        p1_direccion = 'SUBIO' if p1_ajustado > price_p1 else ('BAJO' if p1_ajustado < price_p1 else 'SIN_CAMBIO')
        
        info = {
            'p1_original': price_p1,
            'p1_ajustado': p1_ajustado,
            'p1_movido': p1_ajustado != price_p1,
            'p1_direccion': p1_direccion,
            'p1_diff_pct': round(((p1_ajustado - price_p1) / rango) * 100, 1) if rango > 0 else 0,
            'p1_fuerza': mejor_fuerza_p1,
            'p0_original': max_dinamico_p0,
            'p0_ajustado': p0_ajustado,
            'p0_movido': p0_ajustado != max_dinamico_p0,
            'p0_diff_pct': round(((max_dinamico_p0 - p0_ajustado) / rango) * 100, 1) if rango > 0 else 0,
            'p0_fuerza': mejor_fuerza_p0,
            'rango_original': rango,
            'rango_ajustado': rango_ajustado,
            'rango_reducido_pct': round((1 - rango_ajustado / rango) * 100, 1),
            'n_soportes': len(soportes_con_fuerza),
            'n_resistencias': len(resistencias_con_fuerza)
        }
        
        movido = p1_ajustado != price_p1 or p0_ajustado != max_dinamico_p0
        
        return p1_ajustado, p0_ajustado, movido, info
    
    def _encontrar_niveles_con_fuerza(self, df_klines, lookback=150):
        """
        Encuentra S/R con un score de FUERZA = cuántas velas tocan cada nivel.
        Retorna: [(precio, fuerza), ...] ordenados por fuerza descendente
        """
        if df_klines.empty or len(df_klines) < 20:
            return [], []
        
        df_recent = df_klines.tail(min(lookback, len(df_klines))).reset_index(drop=True)
        
        all_highs = df_recent['high'].values.astype(float)
        all_lows = df_recent['low'].values.astype(float)
        all_closes = df_recent['close'].values.astype(float)
        all_opens = df_recent['open'].values.astype(float)
        
        precio_min = float(min(all_lows))
        precio_max = float(max(all_highs))
        if precio_max <= precio_min:
            return [], []
        
        # Crear bins: cada bin es ~0.5% del rango total
        rango_total = precio_max - precio_min
        bin_size = rango_total / 80  # 80 bins
        if bin_size <= 0:
            return [], []
        
        # === Contar toques en cada zona ===
        # Un "toque" = una vela cuyo high, low, close u open cae en este bin
        zona_toques = {}
        
        for i in range(len(df_recent)):
            # Cada vela "toca" todos los bins entre su low y high
            low_bin = int((all_lows[i] - precio_min) / bin_size)
            high_bin = int((all_highs[i] - precio_min) / bin_size)
            low_bin = max(0, min(low_bin, 79))
            high_bin = max(0, min(high_bin, 79))
            
            # Toques de extremos (mechas) = alta importancia para S/R
            for b in [low_bin, high_bin]:
                zona = precio_min + (b + 0.5) * bin_size
                zona_toques[zona] = zona_toques.get(zona, 0) + 2  # Peso doble para extremos
            
            # Toques de body (open/close) = importancia media
            close_bin = int((all_closes[i] - precio_min) / bin_size)
            open_bin = int((all_opens[i] - precio_min) / bin_size)
            close_bin = max(0, min(close_bin, 79))
            open_bin = max(0, min(open_bin, 79))
            for b in [close_bin, open_bin]:
                zona = precio_min + (b + 0.5) * bin_size
                zona_toques[zona] = zona_toques.get(zona, 0) + 1
        
        # === Filtrar zonas con toques significativos ===
        min_toques = max(6, len(df_recent) * 0.04)  # Al menos 4% de velas
        zonas_fuertes = [(precio, toques) for precio, toques in zona_toques.items() if toques >= min_toques]
        
        # === Agrupar zonas cercanas (dentro del 1.5% del precio) ===
        zonas_fuertes.sort(key=lambda x: x[0])
        grupos = []
        for precio, toques in zonas_fuertes:
            if grupos and abs(precio - grupos[-1][0]) / grupos[-1][0] * 100 <= 1.5:
                # Merge: promedio ponderado por toques
                p_old, t_old = grupos[-1]
                t_total = t_old + toques
                p_new = (p_old * t_old + precio * toques) / t_total
                grupos[-1] = (p_new, t_total)
            else:
                grupos.append((precio, toques))
        
        # === Clasificar como soporte o resistencia ===
        # Un nivel es SOPORTE si más velas rebotan HACIA ARRIBA desde él
        # Un nivel es RESISTENCIA si más velas rebotan HACIA ABAJO desde él
        soportes = []
        resistencias = []
        
        for nivel, fuerza in grupos:
            toques_soporte = 0
            toques_resistencia = 0
            
            for i in range(len(df_recent)):
                # Low toca el nivel = soporte
                if abs(all_lows[i] - nivel) / nivel <= 0.01:
                    toques_soporte += 1
                # High toca el nivel = resistencia
                if abs(all_highs[i] - nivel) / nivel <= 0.01:
                    toques_resistencia += 1
            
            # Asignar según mayoría de toques
            if toques_soporte >= toques_resistencia:
                soportes.append((nivel, fuerza))
            if toques_resistencia >= toques_soporte:
                resistencias.append((nivel, fuerza))
            # Nota: un nivel puede ser AMBOS (flip zone)
        
        # Ordenar por fuerza descendente
        soportes.sort(key=lambda x: x[1], reverse=True)
        resistencias.sort(key=lambda x: x[1], reverse=True)
        
        return soportes, resistencias
    
    def calcular_tp_dinamico_magnetico(self, symbol, pos_data, config, timeframe='1h'):
        """
        TP DINÁMICO MAGNÉTICO:
        Mientras una posición está abierta, ajusta el TP basándose en las 
        resistencias ACTUALES del mercado (que pueden haber cambiado desde la entrada).
        
        Lógica:
        1. Si hay una resistencia fuerte ENTRE el precio actual y el TP original → baja TP a esa resistencia
           (mejor vender donde el precio va a frenar que esperar a un TP que nunca llega)
        2. Si el precio ya superó resistencias y el camino al TP está limpio → mantiene TP original
        3. Si el precio superó el TP original y no hay resistencia cercana → sube TP al siguiente nivel
        4. Siempre garantiza un beneficio mínimo (no baja TP por debajo de la entrada + margen)
        
        Retorna: (tp_ajustado, info_dict) o (None, {}) si no aplica
        """
        try:
            precio_actual = pos_data.get('analysis', {}).get('precio_actual', 0)
            precio_entrada = pos_data.get('precio_entrada_real', 0)
            # CRÍTICO: usar TP ORIGINAL (de valores_originales), NO el del análisis fresco
            # El análisis fresco recalcula P0/P1/TP con datos nuevos, lo que puede dar
            # un TP mucho más alto que el real, impidiendo la venta
            orig = pos_data.get('valores_originales', {})
            tp_original = orig.get('tp', 0)
            if tp_original == 0:
                tp_original = pos_data.get('analysis', {}).get('precio_tp', 0)
            
            if not all([precio_actual > 0, precio_entrada > 0, tp_original > 0]):
                return None, {}
            
            # Obtener klines frescas para detectar resistencias actuales
            df_klines = self.market.get_klines_data(symbol, timeframe, 150)
            if df_klines.empty or len(df_klines) < 30:
                return None, {}
            
            # Encontrar resistencias con fuerza
            _, resistencias = self._encontrar_niveles_con_fuerza(df_klines, lookback=100)
            
            if not resistencias:
                return None, {}
            
            # Beneficio mínimo: no bajar TP por debajo de entrada + 0.5%
            tp_minimo = precio_entrada * 1.005
            
            # === CASO 1: Buscar resistencia fuerte entre precio actual y TP original ===
            resistencias_en_camino = []
            for nivel, fuerza in resistencias:
                # Resistencia entre precio actual (+0.3% margen) y TP original
                if (precio_actual * 1.003) < nivel < tp_original:
                    resistencias_en_camino.append((nivel, fuerza))
            
            if resistencias_en_camino:
                # Usar la resistencia más FUERTE (más tocada), no la más cercana
                resistencias_en_camino.sort(key=lambda x: x[1], reverse=True)
                mejor_resistencia, fuerza = resistencias_en_camino[0]
                
                # Solo ajustar si la resistencia es significativamente fuerte
                # (al menos 8 toques = nivel consolidado)
                if fuerza >= 8:
                    # Ajustar TP justo por debajo de la resistencia (-0.2%)
                    tp_ajustado = mejor_resistencia * 0.998
                    
                    # Validar beneficio mínimo
                    if tp_ajustado >= tp_minimo:
                        beneficio_original = ((tp_original - precio_entrada) / precio_entrada) * 100
                        beneficio_nuevo = ((tp_ajustado - precio_entrada) / precio_entrada) * 100
                        
                        info = {
                            'tipo': 'RESISTENCIA_INTERMEDIA',
                            'tp_original': tp_original,
                            'tp_ajustado': tp_ajustado,
                            'resistencia_nivel': mejor_resistencia,
                            'resistencia_fuerza': fuerza,
                            'beneficio_original_pct': round(beneficio_original, 2),
                            'beneficio_nuevo_pct': round(beneficio_nuevo, 2),
                            'reduccion_tp_pct': round(((tp_original - tp_ajustado) / tp_original) * 100, 2),
                            'n_resistencias_camino': len(resistencias_en_camino)
                        }
                        return tp_ajustado, info
            
            # === CASO 2: Precio superó TP original → buscar siguiente resistencia para extender TP ===
            if precio_actual >= tp_original * 0.995:  # Casi en TP o pasado
                resistencias_arriba = []
                for nivel, fuerza in resistencias:
                    if nivel > precio_actual * 1.002:  # Por encima del precio actual
                        resistencias_arriba.append((nivel, fuerza))
                
                if resistencias_arriba:
                    # Ordenar por cercanía (la primera resistencia por encima)
                    resistencias_arriba.sort(key=lambda x: x[0])
                    siguiente_resistencia, fuerza = resistencias_arriba[0]
                    
                    # Solo extender si la siguiente resistencia está a una distancia razonable
                    # (no más del 3% del precio actual, para no ser avariciosos)
                    distancia_pct = ((siguiente_resistencia - precio_actual) / precio_actual) * 100
                    if 0.3 <= distancia_pct <= 3.0 and fuerza >= 6:
                        tp_extendido = siguiente_resistencia * 0.998
                        beneficio_ext = ((tp_extendido - precio_entrada) / precio_entrada) * 100
                        
                        info = {
                            'tipo': 'TP_EXTENDIDO',
                            'tp_original': tp_original,
                            'tp_ajustado': tp_extendido,
                            'resistencia_nivel': siguiente_resistencia,
                            'resistencia_fuerza': fuerza,
                            'beneficio_extendido_pct': round(beneficio_ext, 2),
                            'extension_pct': round(distancia_pct, 2)
                        }
                        return tp_extendido, info
            
            # === CASO 3: Camino limpio al TP → mantener original ===
            return None, {}
            
        except Exception as e:
            return None, {}
    
    def calcular_rsi(self, df_klines, periodo=14):
        """Calcula RSI (Relative Strength Index) - indicador de sobrecompra/sobreventa"""
        if df_klines.empty or len(df_klines) < periodo + 1:
            return None, {}
        
        close = df_klines['close'].copy()
        delta = close.diff()
        
        gain = delta.where(delta > 0, 0.0)
        loss = (-delta).where(delta < 0, 0.0)
        
        avg_gain = gain.rolling(window=periodo, min_periods=periodo).mean()
        avg_loss = loss.rolling(window=periodo, min_periods=periodo).mean()
        
        # Usar EMA después del primer cálculo (Wilder's smoothing)
        for i in range(periodo + 1, len(avg_gain)):
            avg_gain.iloc[i] = (avg_gain.iloc[i-1] * (periodo - 1) + gain.iloc[i]) / periodo
            avg_loss.iloc[i] = (avg_loss.iloc[i-1] * (periodo - 1) + loss.iloc[i]) / periodo
        
        rs = avg_gain / avg_loss.replace(0, np.finfo(float).eps)
        rsi = 100 - (100 / (1 + rs))
        
        rsi_actual = rsi.iloc[-1]
        rsi_anterior = rsi.iloc[-2] if len(rsi) > 1 else rsi_actual
        
        # Detectar divergencias simples (precio baja pero RSI sube = señal alcista)
        precio_bajando = close.iloc[-1] < close.iloc[-5] if len(close) > 5 else False
        rsi_subiendo = rsi_actual > rsi.iloc[-5] if len(rsi) > 5 else False
        divergencia_alcista = precio_bajando and rsi_subiendo
        
        # RSI girando (pasó de caer a subir)
        rsi_girando_arriba = rsi_actual > rsi_anterior and rsi_anterior < rsi.iloc[-3] if len(rsi) > 3 else False
        
        return rsi_actual, {
            'rsi': round(float(rsi_actual), 2),
            'rsi_anterior': round(float(rsi_anterior), 2),
            'zona': 'SOBREVENDIDO' if rsi_actual < 30 else ('SOBRECOMPRADO' if rsi_actual > 70 else 'NEUTRAL'),
            'divergencia_alcista': divergencia_alcista,
            'girando_arriba': rsi_girando_arriba,
            'tendencia_rsi': 'SUBIENDO' if rsi_actual > rsi_anterior else 'BAJANDO'
        }
    
    def confirmar_volumen(self, df_klines, ventana=20):
        """Verifica si el volumen actual confirma el movimiento (volumen > media)"""
        if df_klines.empty or len(df_klines) < ventana + 1:
            return None, {}
        
        vol = df_klines['volume'].copy()
        vol_media = vol.tail(ventana).mean()
        vol_actual = vol.iloc[-1]
        vol_anterior = vol.iloc[-2]
        
        ratio = vol_actual / vol_media if vol_media > 0 else 0
        
        # Volumen creciente en las últimas 3 velas (señal de interés)
        vol_creciente = all(vol.iloc[-(i+1)] >= vol.iloc[-(i+2)] for i in range(min(2, len(vol)-2)))
        
        return ratio, {
            'ratio': round(float(ratio), 2),
            'vol_creciente': vol_creciente,
            'vol_actual': float(vol_actual),
            'vol_media': float(vol_media),
            'confirmado': ratio >= 1.2  # Volumen 20% por encima de la media
        }
    
    def verificar_ema_tendencia(self, df_klines, ema_rapida=8, ema_lenta=21):
        """Verifica tendencia con cruce de EMAs - ayuda a no comprar en tendencia bajista"""
        if df_klines.empty or len(df_klines) < ema_lenta + 5:
            return None, {}
        
        close = df_klines['close'].copy()
        ema_r = close.ewm(span=ema_rapida, adjust=False).mean()
        ema_l = close.ewm(span=ema_lenta, adjust=False).mean()
        
        ema_r_actual = ema_r.iloc[-1]
        ema_l_actual = ema_l.iloc[-1]
        ema_r_anterior = ema_r.iloc[-2]
        ema_l_anterior = ema_l.iloc[-2]
        
        # Cruce alcista reciente (EMA rápida cruza por encima de lenta)
        cruce_alcista = ema_r_actual > ema_l_actual and ema_r_anterior <= ema_l_anterior
        # EMA rápida por encima = tendencia alcista a corto plazo
        tendencia_alcista = ema_r_actual > ema_l_actual
        # Ambas EMAs subiendo
        ambas_subiendo = ema_r_actual > ema_r_anterior and ema_l_actual > ema_l_anterior
        
        # Distancia entre EMAs como % (mayor distancia = tendencia más fuerte)
        distancia_pct = ((ema_r_actual - ema_l_actual) / ema_l_actual) * 100
        
        return tendencia_alcista, {
            'tendencia_alcista': tendencia_alcista,
            'cruce_alcista': cruce_alcista,
            'ambas_subiendo': ambas_subiendo,
            'distancia_pct': round(float(distancia_pct), 3),
            'ema_rapida': round(float(ema_r_actual), 8),
            'ema_lenta': round(float(ema_l_actual), 8)
        }
    
    def ajustar_fibonacci_magnetico(self, precio_fib, soportes, resistencias, tolerancia=0.02):
        for nivel in soportes + resistencias:
            if abs(precio_fib - nivel) / nivel <= tolerancia:
                return nivel
        return precio_fib
    
    def detectar_patron_recuperacion(self, df_klines, index_p1, index_p0, price_p1, price_p0):
        """
        Detecta el tipo de patrón de recuperación entre P1 (suelo) y P0 (techo).
        
        Patrones detectados:
        - V_SHARP:  Caída y rebote MUY rápidos (ej: flash crash + recovery)
        - V_NORMAL: Caída rápida, rebote moderado (V clásica)
        - U_SHAPE:  Consolidación en el fondo antes de subir (U redondeada)
        - GRADUAL:  Subida lenta y constante sin caída previa clara
        - L_SHAPE:  Caída sin recuperación significativa (lateral)
        
        Retorna: (patron, info_dict) con niveles ajustados recomendados
        """
        if df_klines.empty or index_p1 is None or index_p0 is None:
            return 'DESCONOCIDO', {}
        
        try:
            # Asegurar que los índices son numéricos
            if isinstance(index_p1, (int, np.integer)) and isinstance(index_p0, (int, np.integer)):
                idx_p1 = index_p1
                idx_p0 = index_p0
            else:
                idx_p1 = df_klines.index.get_loc(index_p1) if index_p1 in df_klines.index else None
                idx_p0 = df_klines.index.get_loc(index_p0) if index_p0 in df_klines.index else None
                if idx_p1 is None or idx_p0 is None:
                    return 'DESCONOCIDO', {}
            
            rango_total = price_p0 - price_p1
            if rango_total <= 0 or price_p1 <= 0:
                return 'DESCONOCIDO', {}
            
            # === VELAS DE SUBIDA (P1 → P0) ===
            velas_subida = max(1, abs(idx_p0 - idx_p1))
            
            # === ANALIZAR LA CAÍDA (antes de P1) ===
            # Buscar el máximo local antes de P1 (origen de la caída)
            n_antes = min(velas_subida * 3, idx_p1, 80)
            if n_antes < 2:
                return 'DESCONOCIDO', {}
            
            df_antes = df_klines.iloc[max(0, idx_p1 - n_antes):idx_p1 + 1]
            precio_max_antes = df_antes['high'].max()
            idx_max_antes_local = df_antes['high'].idxmax()
            
            # Posición del máximo en el dataframe original
            if isinstance(idx_max_antes_local, (int, np.integer)):
                velas_caida = max(1, idx_p1 - idx_max_antes_local)
            else:
                pos_max = df_antes.index.get_loc(idx_max_antes_local)
                velas_caida = max(1, len(df_antes) - 1 - pos_max)
            
            # Profundidad de la caída
            caida_pct = ((precio_max_antes - price_p1) / precio_max_antes) * 100 if precio_max_antes > 0 else 0
            
            # === VELOCIDADES ===
            recuperacion_pct = (rango_total / price_p1) * 100
            velocidad_subida = recuperacion_pct / velas_subida    # %/vela subiendo
            velocidad_caida = caida_pct / velas_caida              # %/vela cayendo
            ratio_velocidad = velocidad_subida / velocidad_caida if velocidad_caida > 0 else 1.0
            
            # === SIMETRÍA: primera vs segunda mitad de la subida ===
            df_subida = df_klines.iloc[idx_p1:idx_p0 + 1] if idx_p0 > idx_p1 else df_klines.iloc[idx_p0:idx_p1 + 1]
            mitad = len(df_subida) // 2
            if mitad > 1 and len(df_subida) > 3:
                gan_1ra = df_subida['close'].iloc[mitad] - df_subida['close'].iloc[0]
                gan_2da = df_subida['close'].iloc[-1] - df_subida['close'].iloc[mitad]
                ratio_aceleracion = (gan_2da / gan_1ra) if gan_1ra > 0 else 2.0
            else:
                ratio_aceleracion = 1.0
            
            # === CONSOLIDACIÓN EN FONDO (U-shape detection) ===
            umbral_fondo = price_p1 + (rango_total * 0.15)
            velas_en_fondo = sum(1 for _, row in df_subida.iterrows() if row['low'] <= umbral_fondo)
            pct_en_fondo = velas_en_fondo / max(1, velas_subida)
            
            # === CONTINUIDAD: ¿P0 superó el máximo pre-caída? ===
            recuperacion_total = ((price_p0 - price_p1) / (precio_max_antes - price_p1)) * 100 if (precio_max_antes - price_p1) > 0 else 0
            
            # === CLASIFICAR PATRÓN ===
            if (ratio_velocidad >= 1.3 and velas_subida <= velas_caida * 1.0 
                and pct_en_fondo < 0.25 and caida_pct > 3):
                patron = 'V_SHARP'
            elif (ratio_velocidad >= 0.6 and velas_subida <= velas_caida * 1.8 
                  and pct_en_fondo < 0.35 and caida_pct > 2):
                patron = 'V_NORMAL'
            elif pct_en_fondo >= 0.35:
                patron = 'U_SHAPE'
            elif recuperacion_pct < caida_pct * 0.4:
                patron = 'L_SHAPE'
            else:
                patron = 'GRADUAL'
            
            # === AJUSTES DE NIVELES SEGÚN PATRÓN ===
            if patron == 'V_SHARP':
                # V pronunciada: pullback será poco profundo
                if caida_pct > 10:  # Caída brutal → pullback minúsculo
                    ajuste_entry = 0.382
                    ajuste_tp = 0.0
                else:
                    ajuste_entry = 0.5
                    ajuste_tp = 0.236
                confianza = 'ALTA'
                
            elif patron == 'V_NORMAL':
                ajuste_entry = 0.5
                ajuste_tp = 0.236 if ratio_velocidad > 1.0 else 0.382
                confianza = 'MEDIA-ALTA'
                
            elif patron == 'U_SHAPE':
                # U redondeada: más previsible, niveles estándar ok
                ajuste_entry = 0.618
                ajuste_tp = 0.382
                confianza = 'ALTA'
                
            elif patron == 'L_SHAPE':
                # Sin recuperación: no confiar demasiado
                ajuste_entry = 0.786
                ajuste_tp = 0.5
                confianza = 'BAJA'
                
            else:  # GRADUAL
                ajuste_entry = 0.618
                ajuste_tp = 0.382
                confianza = 'MEDIA'
            
            info = {
                'patron': patron,
                'velas_caida': int(velas_caida),
                'velas_subida': int(velas_subida),
                'caida_pct': round(float(caida_pct), 2),
                'recuperacion_pct': round(float(recuperacion_pct), 2),
                'velocidad_subida_pct_vela': round(float(velocidad_subida), 3),
                'velocidad_caida_pct_vela': round(float(velocidad_caida), 3),
                'ratio_velocidad': round(float(ratio_velocidad), 2),
                'ratio_aceleracion': round(float(ratio_aceleracion), 2),
                'pct_en_fondo': round(float(pct_en_fondo), 2),
                'recuperacion_total_pct': round(float(recuperacion_total), 1),
                'ajuste_entry': ajuste_entry,
                'ajuste_tp': ajuste_tp,
                'confianza': confianza
            }
            
            return patron, info
            
        except Exception as e:
            return 'DESCONOCIDO', {'error': str(e)}
    
    def detectar_estructura_hhhl(self, df_klines, ventana_pivote=5, min_pivotes=4):
        """
        Detecta estructura de Higher Highs / Higher Lows (tendencia alcista)
        o Lower Highs / Lower Lows (tendencia bajista).
        
        Un pivote alto es un máximo local rodeado de máximos menores.
        Un pivote bajo es un mínimo local rodeado de mínimos mayores.
        
        Si los últimos pivotes altos suben Y los pivotes bajos suben → HH/HL (alcista)
        Si bajan ambos → LH/LL (bajista)
        
        Retorna: (estructura, info_dict)
        """
        if df_klines.empty or len(df_klines) < ventana_pivote * 4:
            return 'INDEFINIDO', {}
        
        try:
            highs = df_klines['high'].values
            lows = df_klines['low'].values
            
            # Encontrar pivotes altos (swing highs)
            pivotes_altos = []
            for i in range(ventana_pivote, len(highs) - ventana_pivote):
                es_pivote = all(highs[i] >= highs[i-j] for j in range(1, ventana_pivote+1)) and \
                           all(highs[i] >= highs[i+j] for j in range(1, ventana_pivote+1))
                if es_pivote:
                    pivotes_altos.append({'idx': i, 'price': float(highs[i])})
            
            # Encontrar pivotes bajos (swing lows)
            pivotes_bajos = []
            for i in range(ventana_pivote, len(lows) - ventana_pivote):
                es_pivote = all(lows[i] <= lows[i-j] for j in range(1, ventana_pivote+1)) and \
                           all(lows[i] <= lows[i+j] for j in range(1, ventana_pivote+1))
                if es_pivote:
                    pivotes_bajos.append({'idx': i, 'price': float(lows[i])})
            
            if len(pivotes_altos) < 2 or len(pivotes_bajos) < 2:
                return 'INDEFINIDO', {'pivotes_altos': len(pivotes_altos), 'pivotes_bajos': len(pivotes_bajos)}
            
            # Analizar los últimos N pivotes
            n = min(min_pivotes, len(pivotes_altos), len(pivotes_bajos))
            ultimos_altos = pivotes_altos[-n:]
            ultimos_bajos = pivotes_bajos[-n:]
            
            # Contar HH (Higher High) y HL (Higher Low)
            hh_count = sum(1 for i in range(1, len(ultimos_altos)) 
                          if ultimos_altos[i]['price'] > ultimos_altos[i-1]['price'])
            hl_count = sum(1 for i in range(1, len(ultimos_bajos)) 
                          if ultimos_bajos[i]['price'] > ultimos_bajos[i-1]['price'])
            
            # Contar LH (Lower High) y LL (Lower Low)
            lh_count = sum(1 for i in range(1, len(ultimos_altos)) 
                          if ultimos_altos[i]['price'] < ultimos_altos[i-1]['price'])
            ll_count = sum(1 for i in range(1, len(ultimos_bajos)) 
                          if ultimos_bajos[i]['price'] < ultimos_bajos[i-1]['price'])
            
            total_comparaciones = n - 1
            
            # Clasificar estructura
            if hh_count >= total_comparaciones * 0.6 and hl_count >= total_comparaciones * 0.6:
                estructura = 'ALCISTA_FUERTE'  # HH + HL consistentes
                score_tendencia = 100
            elif hh_count > lh_count and hl_count > ll_count:
                estructura = 'ALCISTA'  # Mayoría HH + HL
                score_tendencia = 75
            elif lh_count >= total_comparaciones * 0.6 and ll_count >= total_comparaciones * 0.6:
                estructura = 'BAJISTA_FUERTE'  # LH + LL consistentes
                score_tendencia = 0
            elif lh_count > hh_count and ll_count > hl_count:
                estructura = 'BAJISTA'  # Mayoría LH + LL
                score_tendencia = 25
            else:
                estructura = 'LATERAL'  # Sin tendencia clara
                score_tendencia = 50
            
            # Detectar RUPTURA de estructura (cambio reciente)
            ruptura = None
            if len(pivotes_bajos) >= 3:
                # Si los 2 últimos lows suben pero antes bajaban → ruptura alcista
                if (pivotes_bajos[-1]['price'] > pivotes_bajos[-2]['price'] and 
                    pivotes_bajos[-2]['price'] < pivotes_bajos[-3]['price']):
                    ruptura = 'GIRO_ALCISTA'
                    score_tendencia = min(100, score_tendencia + 20)
                elif (pivotes_bajos[-1]['price'] < pivotes_bajos[-2]['price'] and 
                      pivotes_bajos[-2]['price'] > pivotes_bajos[-3]['price']):
                    ruptura = 'GIRO_BAJISTA'
                    score_tendencia = max(0, score_tendencia - 20)
            
            info = {
                'estructura': estructura,
                'score_tendencia': score_tendencia,
                'hh_count': hh_count,
                'hl_count': hl_count,
                'lh_count': lh_count,
                'll_count': ll_count,
                'total_pivotes_altos': len(pivotes_altos),
                'total_pivotes_bajos': len(pivotes_bajos),
                'ruptura': ruptura,
                'ultimo_alto': ultimos_altos[-1]['price'] if ultimos_altos else 0,
                'ultimo_bajo': ultimos_bajos[-1]['price'] if ultimos_bajos else 0
            }
            
            return estructura, info
            
        except Exception as e:
            return 'INDEFINIDO', {'error': str(e)}
    
    def detectar_doble_suelo(self, df_klines, tolerancia_pct=2.0, ventana_pivote=5):
        """
        Detecta patrón de Doble Suelo (Double Bottom / W-pattern).
        
        Si el precio toca el mismo nivel de soporte 2 veces con un rebote intermedio,
        es un soporte MUY fuerte → alta probabilidad de subida.
        
        Si P1 coincide con un doble suelo, la confianza sube mucho.
        
        Retorna: (tiene_doble_suelo, info_dict)
        """
        if df_klines.empty or len(df_klines) < 20:
            return False, {}
        
        try:
            lows = df_klines['low'].values
            
            # Encontrar los mínimos locales (swing lows)
            minimos = []
            for i in range(ventana_pivote, len(lows) - ventana_pivote):
                es_minimo = all(lows[i] <= lows[i-j] for j in range(1, ventana_pivote+1)) and \
                           all(lows[i] <= lows[i+j] for j in range(1, ventana_pivote+1))
                if es_minimo:
                    minimos.append({'idx': i, 'price': float(lows[i])})
            
            if len(minimos) < 2:
                return False, {}
            
            # Buscar pares de mínimos al mismo nivel (dentro de tolerancia)
            doble_suelo = None
            for i in range(len(minimos) - 1, 0, -1):  # Buscar desde el más reciente
                for j in range(i - 1, max(i - 5, -1), -1):  # Comparar con los anteriores
                    if j < 0:
                        break
                    precio_1 = minimos[j]['price']
                    precio_2 = minimos[i]['price']
                    diff_pct = abs(precio_1 - precio_2) / precio_1 * 100
                    
                    if diff_pct <= tolerancia_pct:
                        # Verificar que hay un rebote intermedio (neckline)
                        idx_1 = minimos[j]['idx']
                        idx_2 = minimos[i]['idx']
                        if idx_2 - idx_1 >= 4:  # Mínimo 4 velas entre suelos
                            tramo_medio = df_klines.iloc[idx_1:idx_2+1]
                            max_intermedio = tramo_medio['high'].max()
                            rebote_pct = ((max_intermedio - precio_1) / precio_1) * 100
                            
                            if rebote_pct >= 1.5:  # Rebote mínimo 1.5% entre suelos
                                doble_suelo = {
                                    'suelo_1': {'idx': idx_1, 'price': precio_1},
                                    'suelo_2': {'idx': idx_2, 'price': precio_2},
                                    'neckline': float(max_intermedio),
                                    'rebote_pct': round(rebote_pct, 2),
                                    'diferencia_suelos_pct': round(diff_pct, 2),
                                    'velas_entre_suelos': idx_2 - idx_1,
                                    'nivel_soporte': round((precio_1 + precio_2) / 2, 8)
                                }
                                break
                if doble_suelo:
                    break
            
            return doble_suelo is not None, doble_suelo or {}
            
        except Exception as e:
            return False, {'error': str(e)}
    
    def get_punto_1_repetido(self, df_klines, lookback=50):
        if df_klines.empty or len(df_klines) < lookback:
            return None, None
        recent_lows = df_klines['low'].tail(lookback)
        price_range = recent_lows.max() - recent_lows.min()
        if price_range == 0:
            return None, None
        bin_size = price_range / 20
        rounded_lows = np.round(recent_lows / bin_size) * bin_size
        counts = rounded_lows.value_counts()
        if counts.empty:
            return None, None
        mode_val = counts.idxmax()
        mask = (np.round(df_klines['low'] / bin_size) * bin_size) == mode_val
        valid_indices = df_klines[mask].index
        if len(valid_indices) == 0:
            return None, None
        return valid_indices[-1], df_klines.loc[valid_indices[-1], 'low']
    
    def get_punto_1_inflexion(self, df_klines, lookback=50, velas_confirmacion=3, usar_close=False):
        """
        Encuentra P1 como la vela más baja antes del ascenso.
        - usar_close=False: usa el 'low' de la vela (más conservador)
        - usar_close=True: usa el 'close' de la vela
        """
        if df_klines.empty or len(df_klines) < lookback:
            return None, None
        
        df_recent = df_klines.tail(lookback).reset_index(drop=True)
        
        if len(df_recent) < velas_confirmacion + 2:
            return None, None
        
        mejor_idx = None
        mejor_precio = None
        
        # Buscar vela mínima seguida de N velas alcistas
        for i in range(len(df_recent) - velas_confirmacion - 1):
            vela_candidata = df_recent.iloc[i]
            precio_candidato = vela_candidata['close'] if usar_close else vela_candidata['low']
            
            # Verificar que las siguientes N velas son alcistas (cierran más alto)
            es_inflexion = True
            precio_anterior = precio_candidato
            
            for j in range(1, velas_confirmacion + 1):
                vela_siguiente = df_recent.iloc[i + j]
                if vela_siguiente['close'] <= precio_anterior:
                    es_inflexion = False
                    break
                precio_anterior = vela_siguiente['close']
            
            # Verificar que es un mínimo local (vela anterior más alta)
            if es_inflexion and i > 0:
                vela_anterior = df_recent.iloc[i - 1]
                if vela_anterior['low'] < vela_candidata['low']:
                    es_inflexion = False
            
            if es_inflexion:
                if mejor_precio is None or precio_candidato < mejor_precio:
                    mejor_precio = precio_candidato
                    mejor_idx = df_klines.index[-(lookback - i)]
        
        if mejor_idx is None:
            return None, None
        
        return mejor_idx, mejor_precio
    
    def get_punto_1_minimo_absoluto(self, df_klines, lookback=50):
        """
        Encuentra P1 como el mínimo absoluto del periodo.
        El método más simple y conservador.
        """
        if df_klines.empty or len(df_klines) < lookback:
            return None, None
        
        df_recent = df_klines.tail(lookback)
        idx_min = df_recent['low'].idxmin()
        precio_min = df_recent['low'].min()
        
        return idx_min, precio_min
    
    def get_punto_1_soporte_historico(self, df_klines, lookback=200, config=None):
        """
        5º MÉTODO: SOPORTE HISTÓRICO
        En vez de buscar el mínimo reciente, busca el SOPORTE MÁS FUERTE
        (zona donde más velas han rebotado) por debajo del precio actual.
        
        Diferencia clave con otros métodos:
        - Los otros buscan: "¿cuál es el punto más bajo reciente?"
        - Este busca: "¿dónde ha rebotado más veces el precio en la historia?"
        
        Mira mucho más atrás (300-500 velas) para encontrar suelos probados.
        El P1 resultante puede estar MÁS ABAJO que el mínimo reciente si hay
        un soporte histórico fuerte ahí.
        """
        if df_klines.empty or len(df_klines) < 30:
            return None, None
        
        config = config or {}
        lookback_historico = max(lookback, config.get('lookback_soporte_historico', 300))
        min_fuerza = config.get('min_fuerza_soporte_historico', 6)
        
        # Usar lookback extendido para encontrar soportes históricos
        actual_lookback = min(lookback_historico, len(df_klines))
        
        # Encontrar soportes con fuerza usando el método de zonas de congestión
        soportes_con_fuerza, _ = self._encontrar_niveles_con_fuerza(df_klines, lookback=actual_lookback)
        
        if not soportes_con_fuerza:
            # Fallback: usar mínimo absoluto
            return self.get_punto_1_minimo_absoluto(df_klines, lookback=lookback)
        
        precio_actual = df_klines['close'].iloc[-1]
        
        # Filtrar: solo soportes POR DEBAJO del precio actual
        soportes_validos = [(nivel, fuerza) for nivel, fuerza in soportes_con_fuerza 
                           if nivel < precio_actual and fuerza >= min_fuerza]
        
        if not soportes_validos:
            # Si no hay soportes fuertes debajo, usar el soporte más fuerte que exista
            soportes_debajo = [(nivel, fuerza) for nivel, fuerza in soportes_con_fuerza 
                              if nivel < precio_actual]
            if soportes_debajo:
                soportes_validos = soportes_debajo
            else:
                return self.get_punto_1_minimo_absoluto(df_klines, lookback=lookback)
        
        # Ordenar por FUERZA descendente
        soportes_validos.sort(key=lambda x: x[1], reverse=True)
        
        # Elegir el soporte más fuerte
        mejor_soporte_precio = soportes_validos[0][0]
        mejor_soporte_fuerza = soportes_validos[0][1]
        
        # Encontrar el índice de la vela más cercana a este nivel de soporte
        # Buscar la última vela cuyo low esté cerca del soporte
        df_buscar = df_klines.tail(actual_lookback)
        tolerancia_precio = mejor_soporte_precio * 0.01  # 1% de tolerancia
        
        # Buscar velas que tocaron este soporte, tomar la más reciente
        mask_toque = abs(df_buscar['low'] - mejor_soporte_precio) <= tolerancia_precio
        indices_toque = df_buscar[mask_toque].index
        
        if len(indices_toque) > 0:
            # Tomar el toque más reciente como index_p1
            index_p1 = indices_toque[-1]
            price_p1 = mejor_soporte_precio  # Usar el nivel de soporte, no el low exacto
        else:
            # Si no encontramos un toque exacto, buscar la vela más cercana
            diferencias = abs(df_buscar['low'] - mejor_soporte_precio)
            index_p1 = diferencias.idxmin()
            price_p1 = mejor_soporte_precio
        
        return index_p1, price_p1
    
    def get_punto_1_consenso(self, df_klines, lookback=50, config=None):
        """
        Encuentra P1 usando consenso de múltiples métodos.
        Compara resultados y aplica estrategia configurada.
        """
        if config is None:
            config = {}
        
        resultados = []
        velas_confirmacion = config.get('confirmacion_ascenso_velas', 3)
        
        # Obtener P1 de cada método activo
        if config.get('consenso_usar_repetido', True):
            idx, precio = self.get_punto_1_repetido(df_klines, lookback)
            if idx is not None:
                resultados.append({'metodo': 'repetido', 'idx': idx, 'precio': precio})
        
        if config.get('consenso_usar_inflexion_low', True):
            idx, precio = self.get_punto_1_inflexion(df_klines, lookback, velas_confirmacion, usar_close=False)
            if idx is not None:
                resultados.append({'metodo': 'inflexion_low', 'idx': idx, 'precio': precio})
        
        if config.get('consenso_usar_inflexion_close', False):
            idx, precio = self.get_punto_1_inflexion(df_klines, lookback, velas_confirmacion, usar_close=True)
            if idx is not None:
                resultados.append({'metodo': 'inflexion_close', 'idx': idx, 'precio': precio})
        
        if config.get('consenso_usar_minimo', True):
            idx, precio = self.get_punto_1_minimo_absoluto(df_klines, lookback)
            if idx is not None:
                resultados.append({'metodo': 'minimo', 'idx': idx, 'precio': precio})
        
        if config.get('consenso_usar_soporte_historico', True):
            idx, precio = self.get_punto_1_soporte_historico(df_klines, lookback, config=config)
            if idx is not None:
                resultados.append({'metodo': 'soporte_historico', 'idx': idx, 'precio': precio})
        
        if not resultados:
            return None, None, {}
        
        # Si solo hay un resultado, usarlo
        if len(resultados) == 1:
            r = resultados[0]
            return r['idx'], r['precio'], {'metodos_usados': [r['metodo']], 'consenso': False}
        
        tolerancia = config.get('consenso_tolerancia', 0.02)
        estrategia = config.get('consenso_estrategia', 'mas_bajo')
        
        # Encontrar grupos de coincidencia
        # Ordenar por precio de menor a mayor
        resultados_ordenados = sorted(resultados, key=lambda x: x['precio'])
        
        # Agrupar por tolerancia
        grupos = []
        usado = set()
        
        for i, r1 in enumerate(resultados_ordenados):
            if i in usado:
                continue
            grupo = [r1]
            usado.add(i)
            
            for j, r2 in enumerate(resultados_ordenados):
                if j in usado:
                    continue
                # Verificar si están dentro de tolerancia
                diff = abs(r1['precio'] - r2['precio']) / r1['precio']
                if diff <= tolerancia:
                    grupo.append(r2)
                    usado.add(j)
            
            grupos.append(grupo)
        
        # Aplicar estrategia
        if estrategia == 'mas_bajo':
            # Tomar el precio más bajo
            mejor = resultados_ordenados[0]
            return mejor['idx'], mejor['precio'], {
                'metodos_usados': [r['metodo'] for r in resultados],
                'metodo_elegido': mejor['metodo'],
                'consenso': True,
                'estrategia': 'mas_bajo',
                'todos_precios': {r['metodo']: r['precio'] for r in resultados}
            }
        
        elif estrategia == 'minimo_validado':
            # Usar el mínimo absoluto SOLO si al menos otro método lo confirma
            # Si no, usar el grupo con más consenso
            minimo = resultados_ordenados[0]  # El más bajo
            
            # ¿Algún otro método está cerca del mínimo?
            confirmado = False
            metodos_confirman = [minimo['metodo']]
            for r in resultados_ordenados[1:]:
                diff = abs(r['precio'] - minimo['precio']) / minimo['precio']
                if diff <= tolerancia:
                    confirmado = True
                    metodos_confirman.append(r['metodo'])
            
            if confirmado:
                # Mínimo validado por otro método → usarlo
                return minimo['idx'], minimo['precio'], {
                    'metodos_usados': [r['metodo'] for r in resultados],
                    'metodo_elegido': minimo['metodo'],
                    'consenso': True,
                    'validado': True,
                    'metodos_confirman': metodos_confirman,
                    'estrategia': 'minimo_validado',
                    'todos_precios': {r['metodo']: r['precio'] for r in resultados}
                }
            else:
                # Mínimo NO validado (posible mínimo antiguo irrelevante)
                # PERO: si es más reciente que el grupo mayoritario, usarlo
                grupo_mayor = max(grupos, key=len)
                mejor_grupo = min(grupo_mayor, key=lambda x: x['precio'])
                
                diff_pct = (mejor_grupo['precio'] - minimo['precio']) / minimo['precio']
                minimo_es_mas_reciente = minimo['idx'] > mejor_grupo['idx']
                override_threshold = config.get('consenso_override_pct', 3.0) / 100
                
                if config.get('consenso_override_recencia', True) and diff_pct > override_threshold and minimo_es_mas_reciente:
                    # Mínimo reciente no validado pero el mercado YA rompió el soporte mayoritario
                    return minimo['idx'], minimo['precio'], {
                        'metodos_usados': [r['metodo'] for r in resultados],
                        'metodo_elegido': minimo['metodo'],
                        'consenso': False,
                        'validado': False,
                        'override_recencia': True,
                        'estrategia': 'minimo_validado',
                        'todos_precios': {r['metodo']: r['precio'] for r in resultados}
                    }
                
                # Usar grupo mayoritario
                mejor = mejor_grupo
                
                return mejor['idx'], mejor['precio'], {
                    'metodos_usados': [r['metodo'] for r in resultados],
                    'metodo_elegido': mejor['metodo'],
                    'consenso': len(grupo_mayor) >= 2,
                    'validado': False,
                    'minimo_descartado': {'metodo': minimo['metodo'], 'precio': minimo['precio']},
                    'estrategia': 'minimo_validado',
                    'todos_precios': {r['metodo']: r['precio'] for r in resultados}
                }
        
        elif estrategia == 'mayoria':
            # Encontrar el grupo con más coincidencias
            grupo_mayor = max(grupos, key=len)
            
            # MEJORA: Si el mínimo absoluto es MÁS RECIENTE que el grupo mayoritario
            # y significativamente más bajo, preferirlo (el mercado ya demostró que baja más)
            minimo_abs = resultados_ordenados[0]  # El más bajo siempre
            mejor_grupo = min(grupo_mayor, key=lambda x: x['precio'])
            
            override_por_recencia = False
            if config.get('consenso_override_recencia', True) and len(grupo_mayor) >= 2 and minimo_abs not in grupo_mayor:
                # El mínimo está fuera del grupo mayoritario
                diff_pct = (mejor_grupo['precio'] - minimo_abs['precio']) / minimo_abs['precio']
                minimo_es_mas_reciente = minimo_abs['idx'] > mejor_grupo['idx']
                override_threshold = config.get('consenso_override_pct', 3.0) / 100
                
                if diff_pct > override_threshold and minimo_es_mas_reciente:
                    # El mínimo es >3% más bajo Y más reciente → el mercado ya rompió ese soporte
                    override_por_recencia = True
                    mejor = minimo_abs
            
            if not override_por_recencia:
                if len(grupo_mayor) >= 2:
                    # Hay consenso, usar el más bajo del grupo
                    mejor = min(grupo_mayor, key=lambda x: x['precio'])
                else:
                    # No hay consenso de mayoría, usar el más bajo
                    mejor = resultados_ordenados[0]
            
            return mejor['idx'], mejor['precio'], {
                'metodos_usados': [r['metodo'] for r in resultados],
                'metodo_elegido': mejor['metodo'],
                'consenso': len(grupo_mayor) >= 2 and not override_por_recencia,
                'override_recencia': override_por_recencia,
                'estrategia': 'mayoria',
                'grupo_coincidente': [r['metodo'] for r in grupo_mayor],
                'todos_precios': {r['metodo']: r['precio'] for r in resultados}
            }
        
        # Default: más bajo
        mejor = resultados_ordenados[0]
        return mejor['idx'], mejor['precio'], {'metodo_elegido': mejor['metodo']}
    
    def verificar_moneda_agotada(self, df_klines, index_p0, rango, max_dinamico_p0, config):
        """
        Verifica si una moneda está agotada:
        1. Si bajó al punto de entrada (o casi) y luego rebotó al nivel 'Rebote Agotado' → agotada
        2. Si el precio actual ya está por debajo de entrada → agotada
        """
        if not config.get('filtrar_monedas_agotadas', True):
            return False, {}
        
        df_despues_p0 = df_klines.loc[index_p0:]
        if len(df_despues_p0) < 2:
            return False, {}
        
        # Niveles configurables
        nivel_casi_compra = config.get('nivel_casi_compra', 0.65)
        nivel_rebote_agotado = config.get('nivel_rebote_agotado', 0.45)
        nivel_entrada = config.get('entry_fib_level', 0.618)
        
        # Calcular precios
        p1_precio = max_dinamico_p0 - rango
        precio_casi_compra = p1_precio + (rango * (1 - nivel_casi_compra))
        precio_rebote = p1_precio + (rango * (1 - nivel_rebote_agotado))
        precio_entrada_real = p1_precio + (rango * (1 - nivel_entrada))
        precio_actual = df_klines['close'].iloc[-1]
        
        # Verificar mínimo y máximo después de P0
        bajo_minimo = df_despues_p0['low'].min()
        alto_maximo_post_p0 = df_despues_p0['high'].max()
        
        # Debug info base (se incluye en TODOS los returns)
        debug = {
            'p1': p1_precio,
            'p0': max_dinamico_p0,
            'rango': rango,
            'nivel_casi_compra_fib': nivel_casi_compra,
            'nivel_rebote_agotado_fib': nivel_rebote_agotado,
            'nivel_entrada_fib': nivel_entrada,
            'precio_casi_compra': precio_casi_compra,
            'precio_rebote': precio_rebote,
            'precio_entrada_real': precio_entrada_real,
            'precio_actual': precio_actual,
            'bajo_minimo_post_p0': bajo_minimo,
            'alto_maximo_post_p0': alto_maximo_post_p0,
            'velas_post_p0': len(df_despues_p0)
        }
        
        # === CASO 1: Precio actual SIGNIFICATIVAMENTE por debajo de entrada ===
        # Tolerancia 0.3%: si está justo en la entrada (diferencia mínima), NO es agotada
        margen_entrada = precio_entrada_real * 0.003  # 0.3% de tolerancia
        if precio_actual < (precio_entrada_real - margen_entrada):
            debug['razon'] = f'Precio actual ({precio_actual:.6g}) ya debajo de entrada ({precio_entrada_real:.6g})'
            debug['caso'] = 1
            return True, debug
        
        # === CASO 2: Primer armónico completado ===
        llego_a_entrada = bajo_minimo <= precio_entrada_real
        if llego_a_entrada:
            indices_entrada = df_despues_p0[df_despues_p0['low'] <= precio_entrada_real].index
            if len(indices_entrada) > 0:
                idx_toco_entrada = indices_entrada[0]
                df_despues_entrada = df_klines.loc[idx_toco_entrada:]
                
                if len(df_despues_entrada) >= 1:
                    alto_despues = df_despues_entrada['high'].max()
                    debug['alto_rebote_post_entrada'] = alto_despues
                    debug['velas_post_entrada'] = len(df_despues_entrada)
                    
                    if alto_despues >= precio_rebote:
                        debug['razon'] = 'Primer armónico completado: bajó a entrada, rebotó a rebote_agotado+'
                        debug['caso'] = 2
                        return True, debug
            
            debug['razon'] = 'Llegó a entrada, sin rebote significativo aún'
            debug['caso'] = 0
            return False, debug
        
        # === CASO 3: Casi compró y rebotó ===
        toco_casi_compra = bajo_minimo <= precio_casi_compra
        
        if not toco_casi_compra:
            debug['razon'] = 'No tocó nivel de casi compra'
            debug['caso'] = 0
            return False, debug
        
        indices_toco = df_despues_p0[df_despues_p0['low'] <= precio_casi_compra].index
        if len(indices_toco) == 0:
            debug['razon'] = 'No tocó casi compra (sin indices)'
            debug['caso'] = 0
            return False, debug
        
        idx_toco_casi_compra = indices_toco[0]
        df_despues_toque = df_klines.loc[idx_toco_casi_compra:]
        if len(df_despues_toque) < 1:
            debug['razon'] = 'Sin datos después del toque'
            debug['caso'] = 0
            return False, debug
        
        alto_maximo_despues = df_despues_toque['high'].max()
        debug['alto_rebote_post_casi_compra'] = alto_maximo_despues
        reboto_suficiente = alto_maximo_despues >= precio_rebote
        
        if reboto_suficiente:
            debug['razon'] = 'Moneda agotada: casi compró y luego rebotó'
            debug['caso'] = 3
            return True, debug
        
        debug['razon'] = 'No rebotó suficiente'
        debug['caso'] = 0
        return False, debug
    
    def analizar_moneda(self, symbol, config, timeframe='1h', modo_monitoreo=False):
        """
        Analiza una moneda. 
        modo_monitoreo=True: skip filtros RSI/volumen (para monitoreo de órdenes existentes)
        modo_monitoreo=False: análisis completo con filtros (para buscar nuevas oportunidades)
        """
        # Ajuste para obtener datos correctos según el timeframe
        if config.get('usar_multi_temporal', True) and timeframe in config.get('config_temporalidades', {}):
            temp_config = config['config_temporalidades'][timeframe]
            interval_velas = temp_config['velas']
            lookback = temp_config['lookback']
        else:
            interval_velas = '1h'
            lookback = 200
        
        df_klines = self.market.get_klines_data(symbol, interval_velas, lookback)
        if df_klines.empty:
            return {"status": "error", "message": "Sin datos", "timeframe": timeframe}
        
        lookback_p1 = config.get('lookback_p1', 50)
        metodo_p1 = config.get('metodo_p1', 'repetido')
        velas_confirmacion = config.get('confirmacion_ascenso_velas', 3)
        
        # Seleccionar método de detección de P1
        info_consenso = {}
        if metodo_p1 == 'inflexion_low':
            index_p1, price_p1 = self.get_punto_1_inflexion(df_klines, lookback=lookback_p1, velas_confirmacion=velas_confirmacion, usar_close=False)
        elif metodo_p1 == 'inflexion_close':
            index_p1, price_p1 = self.get_punto_1_inflexion(df_klines, lookback=lookback_p1, velas_confirmacion=velas_confirmacion, usar_close=True)
        elif metodo_p1 == 'minimo_absoluto':
            index_p1, price_p1 = self.get_punto_1_minimo_absoluto(df_klines, lookback=lookback_p1)
        elif metodo_p1 == 'consenso':
            index_p1, price_p1, info_consenso = self.get_punto_1_consenso(df_klines, lookback=lookback_p1, config=config)
        elif metodo_p1 == 'soporte_historico':
            index_p1, price_p1 = self.get_punto_1_soporte_historico(df_klines, lookback=lookback_p1, config=config)
        else:  # 'repetido' (default)
            index_p1, price_p1 = self.get_punto_1_repetido(df_klines, lookback=lookback_p1)
        
        if index_p1 is None:
            return {"status": "error", "message": "No P1", "timeframe": timeframe}
        
        punto_1 = {'price': price_p1, 'time': df_klines.loc[index_p1, 'timestamp'], 'info_consenso': info_consenso}
        df_desde_p1 = df_klines.loc[index_p1:]
        max_dinamico_p0 = df_desde_p1['high'].max()
        index_p0 = df_desde_p1['high'].idxmax()
        
        punto_0 = {'price': max_dinamico_p0, 'time': df_klines.loc[index_p0, 'timestamp'], 'is_dynamic': True}
        rango = max_dinamico_p0 - price_p1
        
        # Validar que hay rango suficiente (P0 debe ser mayor que P1)
        if rango <= 0 or (rango / price_p1) < 0.001:
            return {"status": "error", "message": "Rango P0-P1 insuficiente", "timeframe": timeframe}
        
        # === AJUSTE MAGNÉTICO DE P0 Y P1 ===
        # Mueve P0/P1 a soportes/resistencias reales ANTES de calcular Fibonacci
        p0p1_magnetico_info = {}
        if config.get('usar_fib_magnetico', True) and config.get('usar_magnetico_p0p1', True):
            p1_mag, p0_mag, fue_movido, p0p1_magnetico_info = self.ajustar_p0_p1_magnetico(
                price_p1, max_dinamico_p0, df_klines, config
            )
            if fue_movido:
                price_p1 = p1_mag
                max_dinamico_p0 = p0_mag
                rango = max_dinamico_p0 - price_p1
                punto_1 = {'price': price_p1, 'time': df_klines.loc[index_p1, 'timestamp'], 'info_consenso': info_consenso}
                punto_0 = {'price': max_dinamico_p0, 'time': df_klines.loc[index_p0, 'timestamp'], 'is_dynamic': True}
        
        precio_actual = df_klines['close'].iloc[-1]
        
        # NUEVA LÓGICA: Detección mejorada de moneda agotada
        moneda_agotada, detalles_agotada = self.verificar_moneda_agotada(
            df_klines, index_p0, rango, max_dinamico_p0, config
        )
        
        if moneda_agotada:
            return {
                "status": "error", 
                "message": "Moneda agotada", 
                "moneda_agotada": True,
                "detalles_agotada": detalles_agotada,
                "timeframe": timeframe
            }
        
        # Cálculo de niveles Fibonacci
        # Determinar nivel de entrada (normal o alternativo si BTC cae O mercado en BAJADA)
        entry_level = config.get('entry_fib_level', 0.618)
        tp_level_config = config.get('tp_fib_level', 0.382)
        entrada_ajustada_motivo = None
        patron_info = {}
        patron_tipo = 'DESCONOCIDO'
        
        # === DETECCIÓN DE PATRÓN V-RECOVERY ===
        if config.get('usar_deteccion_patron', True):
            patron_tipo, patron_info = self.detectar_patron_recuperacion(
                df_klines, index_p1, index_p0, price_p1, max_dinamico_p0
            )
            
            if patron_info and config.get('patron_ajuste_automatico', True):
                # Usar niveles configurables por patrón (en vez de los hardcoded del detector)
                entry_patron = config.get(f'patron_fib_{patron_tipo}_entry', patron_info.get('ajuste_entry', entry_level))
                tp_patron = config.get(f'patron_fib_{patron_tipo}_tp', patron_info.get('ajuste_tp', tp_level_config))
                
                # Solo ajustar si el patrón sugiere niveles DIFERENTES a los config
                if entry_patron != entry_level or tp_patron != tp_level_config:
                    entry_level = entry_patron
                    tp_level_config = tp_patron
                    entrada_ajustada_motivo = f'PATRON_{patron_tipo}'
        
        # Si está activada la entrada BTC en caída, verificar estado de BTC Y fase mercado
        # (BTC override tiene prioridad sobre patrón: si BTC cae, ser más conservador)
        if config.get('entrada_btc_caida_activa', False):
            try:
                df_btc = self.market.get_klines_data('BTCUSDC', '1h', 24)
                if not df_btc.empty and len(df_btc) >= 2:
                    precio_btc_actual = df_btc['close'].iloc[-1]
                    caida_1h = ((precio_btc_actual - df_btc['close'].iloc[-2]) / df_btc['close'].iloc[-2]) * 100
                    umbral_moderada = config.get('umbral_caida_moderada', -3.0)
                    
                    fase_actual = self.detectar_fase_mercado() if config.get('usar_deteccion_fase', True) else 'DESCONOCIDO'
                    
                    if caida_1h <= umbral_moderada:
                        entry_level = 0.786 + config.get('entrada_btc_caida_ajuste', 0.0)
                        entrada_ajustada_motivo = 'BTC_CAIDA'
                    elif fase_actual == 'BAJADA':
                        entry_level = 0.786 + config.get('entrada_btc_caida_ajuste', 0.0)
                        entrada_ajustada_motivo = 'FASE_BAJADA'
            except:
                pass
        
        precio_entrada_base = price_p1 + (rango * (1 - entry_level))
        
        # Determinar nivel de TP
        tp_level = tp_level_config
        
        # Si está activada la venta BTC en caída, verificar estado de BTC
        if config.get('venta_btc_caida_activa', False):
            try:
                df_btc = self.market.get_klines_data('BTCUSDC', '1h', 24)
                if not df_btc.empty and len(df_btc) >= 2:
                    precio_btc_actual = df_btc['close'].iloc[-1]
                    caida_1h = ((precio_btc_actual - df_btc['close'].iloc[-2]) / df_btc['close'].iloc[-2]) * 100
                    umbral_moderada = config.get('umbral_caida_moderada', -3.0)
                    
                    if caida_1h <= umbral_moderada:
                        tp_level = 0.5 + config.get('venta_btc_caida_ajuste', 0.0)
            except:
                pass
        
        precio_tp_base = price_p1 + (rango * (1 - tp_level))
        precio_reentrada = price_p1 + (rango * (1 - config.get('reentry_fib_level', 0.786)))
        precio_tp2_ext = max_dinamico_p0 + (rango * (config.get('tp2_fib_level', 1.272) - 1))
        precio_safety = price_p1 + (rango * (1 - config.get('safety_fib_level', 0.5)))
        precio_sl_trigger = price_p1 + (rango * (1 - config.get('sl_trigger_fib', 0.886)))
        precio_sl_rebote = price_p1 + (rango * (1 - config.get('sl_rebote_fib', 0.786)))
        precio_sl_definitivo = price_p1 + (rango * (1 - config.get('sl_definitivo_fib', 0.95)))
        
        if config.get('usar_fib_magnetico', True):
            soportes, resistencias = self.encontrar_niveles_clave(df_klines, lookback=100)
            tolerancia = config.get('tolerancia_magnetica', 0.02)
            precio_entrada_base = self.ajustar_fibonacci_magnetico(precio_entrada_base, soportes, resistencias, tolerancia)
            precio_tp_base = self.ajustar_fibonacci_magnetico(precio_tp_base, soportes, resistencias, tolerancia)
            precio_reentrada = self.ajustar_fibonacci_magnetico(precio_reentrada, soportes, resistencias, tolerancia)
        
        beneficio_esperado_pct = ((precio_tp_base - precio_entrada_base) / precio_entrada_base) * 100
        
        # Validar que el beneficio esperado supera el mínimo configurado
        min_beneficio = config.get('min_beneficio_pct', 0.5)
        if beneficio_esperado_pct < min_beneficio:
            return {"status": "error", "message": f"Beneficio {beneficio_esperado_pct:.2f}% < min {min_beneficio}%", "timeframe": timeframe}
        
        # Validar Risk:Reward ratio mínimo
        riesgo_pct = ((precio_entrada_base - precio_sl_definitivo) / precio_entrada_base) * 100 if precio_entrada_base > 0 else 0
        min_rr = config.get('min_risk_reward', 1.0)
        if riesgo_pct > 0:
            risk_reward = beneficio_esperado_pct / riesgo_pct
            if risk_reward < min_rr:
                return {"status": "error", "message": f"R:R {risk_reward:.2f}:1 < min {min_rr}:1 (Gan:{beneficio_esperado_pct:.1f}% vs Riesgo:{riesgo_pct:.1f}%)", "timeframe": timeframe}
        
        fase_mercado = self.detectar_fase_mercado() if config.get('usar_deteccion_fase', True) else 'DESCONOCIDO'
        reentrada_activa = (fase_mercado == 'SUBIDA') if config.get('activar_reentrada_solo_subida', True) else True
        
        # NUEVO: Calcular indicadores de tendencia
        rsi_valor, rsi_info = self.calcular_rsi(df_klines, config.get('rsi_periodo', 14))
        vol_ratio, vol_info = self.confirmar_volumen(df_klines)
        ema_tendencia, ema_info = self.verificar_ema_tendencia(
            df_klines, config.get('ema_rapida', 8), config.get('ema_lenta', 21)
        )
        
        # NUEVO: Estructura de mercado HH/HL y Doble Suelo
        estructura_hhhl, hhhl_info = self.detectar_estructura_hhhl(df_klines)
        tiene_doble_suelo, doble_suelo_info = self.detectar_doble_suelo(df_klines)
        
        # Filtro RSI: no comprar si está sobrecomprado (SOLO en búsqueda, no monitoreo)
        if not modo_monitoreo and config.get('usar_filtro_rsi', True) and rsi_valor is not None:
            rsi_max = config.get('rsi_max_compra', 65)
            if rsi_valor > rsi_max:
                return {
                    "status": "error", 
                    "message": f"RSI {rsi_valor:.0f} > {rsi_max} (sobrecomprado)", 
                    "timeframe": timeframe
                }
        
        # Filtro HH/HL: no comprar en tendencia bajista fuerte (SOLO en búsqueda)
        if not modo_monitoreo and config.get('usar_filtro_hhhl', True):
            if estructura_hhhl == 'BAJISTA_FUERTE':
                return {
                    "status": "error",
                    "message": f"Estructura BAJISTA_FUERTE (LH/LL)",
                    "timeframe": timeframe
                }
            
            # GIRO_BAJISTA = máximo decreciente detectado → cambio de tendencia probable
            if hhhl_info.get('ruptura') == 'GIRO_BAJISTA' and config.get('hhhl_bloquear_bajista_fuerte', True):
                return {
                    "status": "error",
                    "message": f"GIRO_BAJISTA: Máximo decreciente detectado (cambio tendencia)",
                    "timeframe": timeframe
                }
        
        # Filtro PUMP EXHAUSTION: no comprar monedas que ya han subido demasiado
        if not modo_monitoreo:
            max_subida_24h = config.get('max_subida_24h_compra', 30.0)
            try:
                ticker_24h = self.market.get_24h_ticker(symbol)
                if ticker_24h:
                    subida_24h = float(ticker_24h.get('priceChangePercent', 0))
                    if subida_24h > max_subida_24h:
                        return {
                            "status": "error",
                            "message": f"Pump exhaustion: +{subida_24h:.1f}% en 24h > máx {max_subida_24h:.0f}%",
                            "timeframe": timeframe
                        }
            except:
                pass
        
        # Filtro LOWER HIGH: P0 actual vs máximo reciente más alto
        if not modo_monitoreo and config.get('filtrar_lower_high', True):
            try:
                # Buscar si hay un máximo anterior más alto en las últimas velas
                df_extended = self.market.get_klines_data(symbol, timeframe, int(lookback_p1 * 2))
                if not df_extended.empty and len(df_extended) > lookback_p1:
                    max_previo = df_extended['high'].iloc[:-lookback_p1].max()
                    if max_previo > max_dinamico_p0 * 1.02:  # P0 actual es >2% más bajo que un máximo previo
                        ratio_lower = max_dinamico_p0 / max_previo
                        if ratio_lower < 0.95:  # P0 actual es >5% más bajo → lower high claro
                            return {
                                "status": "error",
                                "message": f"Lower High: P0 {fmt_precio(max_dinamico_p0)} < Máx previo {fmt_precio(max_previo)} ({(1-ratio_lower)*100:.1f}% más bajo)",
                                "timeframe": timeframe
                            }
            except:
                pass
        
        estado_orden = "PENDIENTE"
        if config.get('modo_avanzado_activo', False) and reentrada_activa:
            if precio_actual <= precio_entrada_base:
                estado_orden = "EN ENTRADA"
            elif precio_actual <= precio_reentrada:
                estado_orden = "EN REENTRADA"
        else:
            if precio_actual <= precio_entrada_base:
                estado_orden = "EN ENTRADA"
        
        rr_ratio = (beneficio_esperado_pct / riesgo_pct) if riesgo_pct > 0 else 99
        
        return {
            "status": "OK", "symbol": symbol, "timeframe": timeframe, "punto_1": punto_1, "punto_0": punto_0,
            "max_dinamico": max_dinamico_p0, "precio_entrada": precio_entrada_base, "precio_tp": precio_tp_base,
            "beneficio_esperado_pct": beneficio_esperado_pct, "precio_actual": precio_actual,
            "riesgo_pct": riesgo_pct, "risk_reward": rr_ratio,
            "estado_orden": estado_orden, "rango": rango, "precio_reentrada": precio_reentrada,
            "precio_tp2": precio_tp2_ext, "precio_safety": precio_safety, "precio_sl_trigger": precio_sl_trigger,
            "precio_sl_rebote": precio_sl_rebote, "precio_sl_definitivo": precio_sl_definitivo,
            "timestamp_analisis": datetime.now(), "fase_mercado": fase_mercado, "reentrada_activa": reentrada_activa,
            "moneda_agotada": False,
            "rsi": rsi_info, "rsi_valor": rsi_valor,
            "volumen": vol_info, "vol_ratio": vol_ratio,
            "ema": ema_info, "ema_tendencia": ema_tendencia,
            "entrada_ajustada_motivo": entrada_ajustada_motivo,
            "patron_recuperacion": patron_tipo,
            "patron_info": patron_info,
            "entry_level_usado": entry_level,
            "tp_level_usado": tp_level,
            "estructura_hhhl": estructura_hhhl,
            "hhhl_info": hhhl_info,
            "doble_suelo": tiene_doble_suelo,
            "doble_suelo_info": doble_suelo_info,
            "p0p1_magnetico": p0p1_magnetico_info
        }
    
    def calcular_score(self, symbol, top_100_df, analysis_data, estrategia, config=None):
        if config is None:
            config = {}
        score, detalles = 0, {}
        if analysis_data['status'] == 'OK':
            distancia = abs((analysis_data['precio_actual'] - analysis_data['precio_entrada']) / analysis_data['precio_entrada']) * 100
            proximidad_score = max(0, 100 - (distancia * 5))
            detalles['proximidad'] = round(proximidad_score, 2)
        row = top_100_df[top_100_df['symbol'] == symbol]
        if not row.empty:
            momentum = row['priceChangePercent'].values[0]
            detalles['momentum'] = round(min(100, max(0, momentum * 10)), 2)
            detalles['volumen'] = round((row['quoteVolume'].values[0] / top_100_df['quoteVolume'].max()) * 100, 2)
        if analysis_data['status'] == 'OK' and analysis_data['rango'] > 0:
            detalles['volatilidad'] = round(min(100, (analysis_data['rango'] / analysis_data['precio_actual']) * 100 * 20), 2)
        
        # NUEVO: Score RSI (mayor si está en zona sobrevendido, 0 si sobrecomprado)
        rsi_valor = analysis_data.get('rsi_valor')
        if rsi_valor is not None and config.get('usar_filtro_rsi', True):
            if rsi_valor <= 30:
                rsi_score = 100  # Sobrevendido = ideal para comprar
            elif rsi_valor <= 40:
                rsi_score = 80
            elif rsi_valor <= 50:
                rsi_score = 60
            elif rsi_valor <= 60:
                rsi_score = 40
            elif rsi_valor <= 70:
                rsi_score = 20
            else:
                rsi_score = 0   # Sobrecomprado = no comprar
            
            # Bonus por divergencia alcista (precio baja pero RSI sube)
            rsi_info = analysis_data.get('rsi', {})
            if rsi_info.get('divergencia_alcista', False):
                rsi_score = min(100, rsi_score + 20)
            if rsi_info.get('girando_arriba', False):
                rsi_score = min(100, rsi_score + 10)
            
            detalles['rsi'] = round(rsi_score, 2)
        
        # NUEVO: Score confirmación de volumen
        vol_info = analysis_data.get('volumen', {})
        if vol_info and config.get('usar_confirmacion_volumen', True):
            vol_ratio = vol_info.get('ratio', 0)
            if vol_ratio >= 2.0:
                vol_score = 100  # Mucho volumen = interés fuerte
            elif vol_ratio >= 1.5:
                vol_score = 80
            elif vol_ratio >= 1.2:
                vol_score = 60
            elif vol_ratio >= 1.0:
                vol_score = 40
            else:
                vol_score = 20  # Bajo volumen = poca convicción
            
            if vol_info.get('vol_creciente', False):
                vol_score = min(100, vol_score + 15)
            
            detalles['vol_confirm'] = round(vol_score, 2)
        
        # NUEVO: Score EMA tendencia
        ema_info = analysis_data.get('ema', {})
        if ema_info and config.get('usar_filtro_ema_tendencia', True):
            ema_score = 50  # Base neutral
            if ema_info.get('tendencia_alcista', False):
                ema_score = 75
            if ema_info.get('cruce_alcista', False):
                ema_score = 100  # Cruce reciente = señal muy buena
            if ema_info.get('ambas_subiendo', False):
                ema_score = min(100, ema_score + 15)
            if not ema_info.get('tendencia_alcista', True):
                ema_score = 25  # Tendencia bajista = penalizar
            
            detalles['ema_tend'] = round(ema_score, 2)
        
        # NUEVO: Score estructura HH/HL
        hhhl_info = analysis_data.get('hhhl_info', {})
        if hhhl_info and config.get('usar_filtro_hhhl', True):
            hhhl_score = hhhl_info.get('score_tendencia', 50)
            
            # Bonus por ruptura/giro
            ruptura = hhhl_info.get('ruptura')
            if ruptura == 'GIRO_ALCISTA':
                hhhl_score = min(100, hhhl_score + 15)
            elif ruptura == 'GIRO_BAJISTA':
                hhhl_score = max(0, hhhl_score - 15)
            
            detalles['hhhl'] = round(hhhl_score, 2)
        
        # NUEVO: Bonus por Doble Suelo (soporte fuerte)
        if analysis_data.get('doble_suelo', False):
            detalles['doble_suelo'] = 100  # Soporte confirmado = máximo score
        
        # Calcular score final con pesos
        if estrategia == "A":
            score = (detalles.get('proximidad', 0) * 0.55) + (detalles.get('momentum', 0) * 0.15) + (detalles.get('volumen', 0) * 0.05)
        elif estrategia == "B":
            score = (detalles.get('momentum', 0) * 0.55) + (detalles.get('proximidad', 0) * 0.15) + (detalles.get('volumen', 0) * 0.05)
        else:  # C (equilibrado)
            score = (detalles.get('proximidad', 0) * 0.30) + (detalles.get('momentum', 0) * 0.20) + (detalles.get('volumen', 0) * 0.10) + (detalles.get('volatilidad', 0) * 0.05)
        
        # Añadir componentes de tendencia (comunes a todas las estrategias)
        rsi_peso = config.get('rsi_peso_score', 0.15) if config.get('usar_filtro_rsi', True) else 0
        vol_peso = config.get('volumen_peso_score', 0.10) if config.get('usar_confirmacion_volumen', True) else 0
        ema_peso = 0.05 if config.get('usar_filtro_ema_tendencia', True) else 0
        hhhl_peso = 0.10 if config.get('usar_filtro_hhhl', True) else 0
        doble_suelo_bonus = 0.05 if analysis_data.get('doble_suelo', False) else 0
        
        score += detalles.get('rsi', 50) * rsi_peso
        score += detalles.get('vol_confirm', 50) * vol_peso
        score += detalles.get('ema_tend', 50) * ema_peso
        score += detalles.get('hhhl', 50) * hhhl_peso
        score += detalles.get('doble_suelo', 0) * doble_suelo_bonus
        
        return round(score, 2), detalles

# ============================================
# GESTIÓN DE POSICIONES
# ============================================

# Niveles Fibonacci ordenados de mayor a menor (de P1 a extensión)
NIVELES_FIB = [1.0, 0.886, 0.786, 0.618, 0.5, 0.382, 0.236, 0.0, -0.272]

def calcular_escalon_actual(precio_actual, p1_precio, p0_precio, config):
    """
    Calcula en qué escalón Fibonacci está el precio actual.
    Retorna el índice del escalón (0 = más bajo, mayor = más alto)
    """
    if p0_precio <= p1_precio:
        return 0
    
    rango = p0_precio - p1_precio
    
    # Calcular nivel Fibonacci actual del precio
    nivel_actual = 1 - ((precio_actual - p1_precio) / rango)
    
    # Encontrar el escalón (nivel Fibonacci superado)
    escalon = 0
    for i, nivel in enumerate(NIVELES_FIB):
        if nivel_actual <= nivel:
            escalon = i
        else:
            break
    
    return escalon

def calcular_sl_escalon(posicion, config, p1_original=None, p0_original=None):
    """
    Calcula los niveles de SL dinámicos según el escalón actual.
    Usa P1/P0 ORIGINALES (del momento de compra), no del análisis fresco.
    """
    analysis = posicion.get('analysis', {})
    precio_actual = analysis.get('precio_actual', 0)
    precio_entrada = posicion.get('precio_entrada_real', 0)
    
    # Usar P1/P0 originales pasados como parámetro, o fallback a analysis
    p1_precio = p1_original if p1_original and p1_original > 0 else analysis.get('punto_1', {}).get('price', 0)
    p0_precio = p0_original if p0_original and p0_original > 0 else analysis.get('punto_0', {}).get('price', 0)
    
    if p0_precio <= p1_precio or precio_actual <= 0:
        return None
    
    rango = p0_precio - p1_precio
    
    # Verificar si escalones están activos
    if not config.get('escalones_activo', True):
        return None
    
    # Calcular escalón actual
    escalon_actual = calcular_escalon_actual(precio_actual, p1_precio, p0_precio, config)
    
    # Guardar máximo escalón alcanzado (no baja)
    max_escalon = posicion.get('max_escalon_alcanzado', 0)
    escalon_previo = max_escalon
    if escalon_actual > max_escalon:
        posicion['max_escalon_alcanzado'] = escalon_actual
        max_escalon = escalon_actual
        # Marcar que subió de escalón (para logging externo)
        posicion['escalon_subio'] = True
        posicion['escalon_previo'] = escalon_previo
    else:
        posicion['escalon_subio'] = False
    
    # Nivel de activación (por defecto 0.5, que es escalón ~4)
    nivel_activacion = config.get('escalon_activacion', 0.5)
    escalon_activacion = 0
    for i, nivel in enumerate(NIVELES_FIB):
        if nivel_activacion >= nivel:
            escalon_activacion = i
            break
    
    # Si no hemos alcanzado el nivel de activación, no aplicar escalones
    # CORREGIDO: Activar cuando max_escalon >= escalon_activacion (antes era >)
    if max_escalon < escalon_activacion:
        return None
    
    # Calcular cuántos escalones hemos subido desde la activación
    # CORREGIDO: Mínimo 1 si hemos alcanzado el nivel de activación
    escalones_subidos = max(1, max_escalon - escalon_activacion + 1)
    
    # Obtener ajustes (heredados o personalizados)
    if config.get('escalones_ajustes_personalizados', False):
        trigger_base = config.get('escalon_trigger_base', 0.618)
        trigger_ajuste = config.get('escalon_trigger_ajuste', 0.005)
        rebote_base = config.get('escalon_rebote_base', 0.5)
        rebote_ajuste = config.get('escalon_rebote_ajuste', 0.011)
        definitivo_base = config.get('escalon_definitivo_base', 0.618)
        definitivo_ajuste = config.get('escalon_definitivo_ajuste', 0.005)
    else:
        # Heredar del SL normal pero subir un escalón en la base
        trigger_base_normal = config.get('sl_trigger_fib', 0.886)
        rebote_base_normal = config.get('sl_rebote_fib', 0.786)
        definitivo_base_normal = config.get('sl_definitivo_fib', 0.95)
        
        # Calcular ajustes del SL normal
        trigger_base_idx = min(range(len(NIVELES_FIB)), key=lambda i: abs(NIVELES_FIB[i] - trigger_base_normal))
        rebote_base_idx = min(range(len(NIVELES_FIB)), key=lambda i: abs(NIVELES_FIB[i] - rebote_base_normal))
        definitivo_base_idx = min(range(len(NIVELES_FIB)), key=lambda i: abs(NIVELES_FIB[i] - definitivo_base_normal))
        
        trigger_ajuste = trigger_base_normal - NIVELES_FIB[trigger_base_idx]
        rebote_ajuste = rebote_base_normal - NIVELES_FIB[rebote_base_idx]
        definitivo_ajuste = definitivo_base_normal - NIVELES_FIB[definitivo_base_idx]
        
        # Subir la base según escalones subidos
        # CORREGIDO: Sumar escalones al índice (mover hacia Fib más bajo = precio más alto)
        # Antes restaba, lo que movía el SL hacia P1 (precio más BAJO) - exactamente al revés
        nuevo_trigger_idx = min(len(NIVELES_FIB) - 1, trigger_base_idx + escalones_subidos)
        nuevo_rebote_idx = min(len(NIVELES_FIB) - 1, rebote_base_idx + escalones_subidos)
        nuevo_definitivo_idx = min(len(NIVELES_FIB) - 1, definitivo_base_idx + escalones_subidos)
        
        trigger_base = NIVELES_FIB[nuevo_trigger_idx]
        rebote_base = NIVELES_FIB[nuevo_rebote_idx]
        definitivo_base = NIVELES_FIB[nuevo_definitivo_idx]
    
    # Calcular precios de SL escalón
    sl_trigger_nivel = trigger_base + trigger_ajuste
    sl_rebote_nivel = rebote_base + rebote_ajuste
    sl_definitivo_nivel = definitivo_base + definitivo_ajuste
    
    # Convertir niveles Fib a precios
    sl_trigger_precio = p1_precio + (rango * (1 - sl_trigger_nivel))
    sl_rebote_precio = p1_precio + (rango * (1 - sl_rebote_nivel))
    sl_definitivo_precio = p1_precio + (rango * (1 - sl_definitivo_nivel))
    
    return {
        'escalon_actual': escalon_actual,
        'max_escalon': max_escalon,
        'escalones_subidos': escalones_subidos,
        'sl_trigger_precio': sl_trigger_precio,
        'sl_trigger_nivel': sl_trigger_nivel,
        'sl_rebote_precio': sl_rebote_precio,
        'sl_rebote_nivel': sl_rebote_nivel,
        'sl_definitivo_precio': sl_definitivo_precio,
        'sl_definitivo_nivel': sl_definitivo_nivel,
        'proteccion_activa': True
    }

def calcular_tp_reentradas(posicion, config):
    """
    Si reentradas progresivas están activas, devuelve el TP extendido.
    """
    if not config.get('reentradas_progresivas', False):
        return None
    
    analysis = posicion.get('analysis', {})
    p1_precio = analysis.get('punto_1', {}).get('price', 0)
    p0_precio = analysis.get('punto_0', {}).get('price', 0)
    
    if p0_precio <= p1_precio:
        return None
    
    rango = p0_precio - p1_precio
    tp_max_nivel = config.get('tp_maximo_reentradas', -0.272)
    
    # Calcular precio del TP máximo (nivel negativo = extensión por encima de P0)
    tp_max_precio = p1_precio + (rango * (1 - tp_max_nivel))
    
    return {
        'tp_max_precio': tp_max_precio,
        'tp_max_nivel': tp_max_nivel
    }

def calcular_tamano_posicion(config):
    if config['modo_capital'] == 'porcentaje':
        return (config['balance_disponible'] * config['capital_porcentaje']) / 100 if config['balance_disponible'] > 0 else 100
    else:
        return config['capital_fijo']

def evaluar_stop_loss_dinamico(posicion, config, sl_trigger_orig=None, sl_definitivo_orig=None):
    analysis = posicion['analysis']
    precio_actual = analysis['precio_actual']
    precio_entrada_real = posicion.get('precio_entrada_real', analysis['precio_entrada'])
    
    # Usar SL originales si se proporcionan, sino del análisis fresco (fallback)
    precio_sl_trigger = sl_trigger_orig if sl_trigger_orig and sl_trigger_orig > 0 else analysis.get('precio_sl_trigger', 0)
    precio_sl_rebote = analysis.get('precio_sl_rebote', 0)  # Rebote puede ser del fresco
    precio_sl_definitivo = sl_definitivo_orig if sl_definitivo_orig and sl_definitivo_orig > 0 else analysis.get('precio_sl_definitivo', 0)
    
    estado_sl = {'estado': 'OK', 'perdida_actual': ((precio_actual - precio_entrada_real) / precio_entrada_real) * 100, 'accion': None}
    if precio_actual <= precio_sl_trigger:
        if posicion.get('sl_esperando_rebote', False):
            velas_esperadas = posicion.get('sl_velas_esperadas', 0) + 1
            posicion['sl_velas_esperadas'] = velas_esperadas
            if precio_actual >= precio_sl_rebote:
                estado_sl.update({'estado': 'REBOTE_EXITOSO', 'accion': 'VENDER_EN_REBOTE', 'precio_venta': precio_sl_rebote})
                return estado_sl
            if velas_esperadas >= config.get('sl_timeout_candles', 5):
                estado_sl.update({'estado': 'SL_DEFINITIVO', 'accion': 'VENDER_EN_FIBONACCI', 'precio_venta': precio_sl_definitivo})
                return estado_sl
            estado_sl.update({'estado': 'ESPERANDO_REBOTE', 'velas_restantes': config.get('sl_timeout_candles', 5) - velas_esperadas})
        else:
            posicion.update({'sl_esperando_rebote': True, 'sl_velas_esperadas': 0})
            estado_sl.update({'estado': 'TRIGGER_ACTIVADO', 'precio_rebote_objetivo': precio_sl_rebote})
    return estado_sl

# ============================================
# BOT PRINCIPAL (THREADING)
# ============================================

class TradingBot:
    """Bot de trading que corre en un hilo separado"""
    
    def __init__(self):
        self.config = load_config()
        self.start_time = None  # Se establece cuando se llama a start()
        
        self.market = MarketDataManager()
        self.analyzer = TechnicalAnalyzer(self.market)
        self.orders = BinanceOrderManager(self.market)
        self.stats = EstadisticasManager()
        self.blacklist = BlacklistManager()
        
        # Estado del bot
        self.running = False
        self.paused = False
        self._thread = None
        self._stop_event = threading.Event()
        
        # Datos compartidos (thread-safe)
        self._lock = threading.Lock()
        self.open_positions = {}
        self.ordenes_pendientes = {}
        self.oportunidades = []
        self.logs = queue.Queue(maxsize=500)
        self.last_update = None
        self.btc_status = {}
        self.fase_mercado = 'DESCONOCIDO'
        
        # Cola de espera para monedas (para reemplazar agotadas)
        self.cola_espera = []
        
        # Estado de protección por pérdidas
        self.modo_proteccion_activado = False
        
        # Anti-crash: contador de SLs por ciclo (para no comprar durante crash)
        self._sl_hits_este_ciclo = 0
        
        # Control de ciclos escalonados (rotar temporalidades)
        self._ciclo_contador = 0
        self._ultimo_nivel_btc_logueado = None
        
        # Cooldown para logs de "agotada" (evitar spam)
        self._agotada_cooldown = {}  # {symbol_tf: timestamp}
        
        # Cargar estado guardado (posiciones, órdenes pendientes)
        self._load_state()
    
    def _save_state(self):
        """Guarda posiciones y órdenes a disco para sobrevivir reinicios"""
        try:
            state = {
                'open_positions': self.open_positions.copy(),
                'ordenes_pendientes': self.ordenes_pendientes.copy(),
                'cola_espera': self.cola_espera.copy(),
                'modo_proteccion_activado': self.modo_proteccion_activado,
            }
            with open('bot_state.json', 'w') as f:
                json.dump(state, f, indent=2, default=str)
        except Exception as e:
            pass  # No bloquear el bot si falla el guardado
    
    def _load_state(self):
        """Carga estado guardado desde disco"""
        try:
            with open('bot_state.json', 'r') as f:
                state = json.load(f)
            
            self.open_positions = state.get('open_positions', {})
            self.ordenes_pendientes = state.get('ordenes_pendientes', {})
            self.cola_espera = state.get('cola_espera', [])
            self.modo_proteccion_activado = state.get('modo_proteccion_activado', False)
            
            n_pos = len(self.open_positions)
            n_ord = len(self.ordenes_pendientes)
            n_cola = len(self.cola_espera)
            if n_pos + n_ord + n_cola > 0:
                self.log(f"📂 Estado restaurado: {n_pos} posiciones, {n_ord} órdenes, {n_cola} en cola", "SUCCESS")
        except FileNotFoundError:
            pass  # Primera ejecución, no hay estado guardado
        except Exception as e:
            self.log(f"⚠️ Error cargando estado: {e}", "WARNING")
        
    def log(self, mensaje, nivel='INFO'):
        """Añade mensaje al log (thread-safe) en UTC"""
        from datetime import timezone as _tz, timedelta as _td
        timestamp = datetime.now(_tz(timedelta(hours=1))).strftime("%Y-%m-%d %H:%M:%S UTC+1")
        entry = {'timestamp': timestamp, 'nivel': nivel, 'mensaje': mensaje}
        try:
            if self.logs.full():
                self.logs.get_nowait()
            self.logs.put_nowait(entry)
        except:
            pass
    
    def get_logs(self):
        """Obtiene todos los logs actuales"""
        logs = []
        temp_logs = []
        while not self.logs.empty():
            try:
                log = self.logs.get_nowait()
                logs.append(log)
                temp_logs.append(log)
            except:
                break
        # Volver a poner los logs en la cola
        for log in temp_logs:
            try:
                self.logs.put_nowait(log)
            except:
                break
        return logs
    
    def start(self):
        """Inicia el bot"""
        if self.running:
            return False
        self._stop_event.clear()
        self.running = True
        self.paused = False
        self.start_time = datetime.now()  # Usar hora local para consistencia con UI
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        self.log("🚀 Bot iniciado", "SUCCESS")
        # Notificar arranque por Telegram
        config = self.config
        if config.get('telegram_bot_token') and config.get('telegram_chat_id'):
            modo = "DEMO" if config.get('modo_demo', True) else "REAL"
            enviar_telegram(config['telegram_bot_token'], config['telegram_chat_id'],
                f"🤖 TradingBro 1.0\n✅ Bot conectado!\n📊 Modo: {modo}", config, 'general')
        return True
    
    def stop(self):
        """Detiene el bot"""
        if not self.running:
            return False
        self._stop_event.set()
        self.running = False
        if self._thread:
            self._thread.join(timeout=5)
        self._save_state()
        self.log("🛑 Bot detenido", "WARNING")
        return True
    
    def pause(self):
        """Pausa el bot"""
        self.paused = True
        self.log("⏸️ Bot pausado", "INFO")
    
    def resume(self):
        """Reanuda el bot"""
        self.paused = False
        self.log("▶️ Bot reanudado", "INFO")
    
    def calcular_stats_recientes(self, ventana=5):
        """Calcula % ganadoras/perdedoras de últimas N operaciones"""
        ops = self.stats.estadisticas.get('operaciones_completadas', [])[-ventana:]
        if len(ops) < 3:  # Mínimo 3 operaciones para evaluar
            return None
        
        ganadoras = sum(1 for op in ops if op.get('beneficio_pct', 0) > 0)
        return {
            'total': len(ops),
            'ganadoras': ganadoras,
            'perdedoras': len(ops) - ganadoras,
            'pct_ganadoras': (ganadoras / len(ops)) * 100,
            'pct_perdedoras': ((len(ops) - ganadoras) / len(ops)) * 100
        }
    
    def _ejecutar_proteccion_perdidas(self, config):
        """Ejecuta protección por entradas fallidas.
        ACTIVAR: si X% de últimas N ops son pérdidas → DEMO
        DESACTIVAR: tras N ops ganadoras en DEMO → REAL"""
        if not config.get('proteccion_perdidas_activa', True):
            return
        
        ventana = config.get('ventana_operaciones', 5)
        umbral_perdidas = config.get('umbral_perdidas_pct', 75)
        ops_para_volver = config.get('proteccion_ops_para_volver', 1)
        
        stats = self.calcular_stats_recientes(ventana)
        if stats is None:
            return
        
        # Si estamos en modo protección, contar ops ganadoras desde activación
        if self.modo_proteccion_activado:
            ops_desde_proteccion = getattr(self, '_ops_ganadoras_proteccion', 0)
            if ops_desde_proteccion >= ops_para_volver:
                self.config['modo_demo'] = False
                self.modo_proteccion_activado = False
                self._ops_ganadoras_proteccion = 0
                save_config(self.config)
                self.log(f"🟢 Protección desactivada: {ops_desde_proteccion} op(s) ganadora(s). Volviendo a MODO REAL", "SUCCESS")
                if self.config.get('telegram_bot_token') and self.config.get('telegram_chat_id'):
                    enviar_telegram(self.config['telegram_bot_token'], self.config['telegram_chat_id'], 
                        f"🟢 Bot vuelve a MODO REAL\n✅ {ops_desde_proteccion} operacion(es) ganadora(s) en demo",
                        self.config, 'proteccion')
            return
        
        # Si perdidas superan umbral, activar protección
        if not self.modo_proteccion_activado and stats['pct_perdedoras'] >= umbral_perdidas:
            self.log(f"🛑 PROTECCIÓN ACTIVADA: {stats['pct_perdedoras']:.0f}% pérdidas en últimas {ventana} ops", "WARNING")
            
            # Cerrar posiciones abiertas EN PÉRDIDA (preservar las ganadoras)
            with self._lock:
                cerradas_perdida = 0
                preservadas = 0
                for symbol in list(self.open_positions.keys()):
                    pos = self.open_positions[symbol]
                    precio_entrada = pos.get('precio_entrada_real', 0)
                    precio_actual = pos.get('analysis', {}).get('precio_actual', 0)
                    
                    if precio_entrada > 0 and precio_actual > 0:
                        pnl_pct = ((precio_actual - precio_entrada) / precio_entrada) * 100
                        if pnl_pct > 0.5:  # Si tiene >0.5% de beneficio, preservar
                            self.log(f"🛡️ {symbol} preservada (+{pnl_pct:.1f}%) - protección no cierra ganadoras", "INFO")
                            preservadas += 1
                            continue
                    
                    self._cerrar_posicion(symbol, 'PROTECCION_PERDIDAS', config)
                    cerradas_perdida += 1
                
                if preservadas > 0:
                    self.log(f"📊 Protección: {cerradas_perdida} cerradas, {preservadas} preservadas (en beneficio)", "INFO")
            
            # Cambiar a modo demo
            self.config['modo_demo'] = True
            self.modo_proteccion_activado = True
            save_config(self.config)
            
            # CANCELAR todas las LIMIT BUY en Binance (evitar órdenes huérfanas)
            if self.orders._is_configured():
                for sym, ord_data in list(self.ordenes_pendientes.items()):
                    if ord_data.get('binance_order_id'):
                        self._cancelar_orden_binance_pendiente(sym, ord_data)
                        ord_data.pop('binance_order_id', None)
                        ord_data.pop('binance_price', None)
                        ord_data.pop('binance_qty', None)
                        self.log(f"🗑️ {sym} - LIMIT BUY cancelada (protección → DEMO)", "INFO")
            
            self.log("⚠️ Bot en MODO DEMO por protección. Sigue operando virtualmente.", "WARNING")
            
            if self.config.get('telegram_bot_token') and self.config.get('telegram_chat_id'):
                enviar_telegram(self.config['telegram_bot_token'], self.config['telegram_chat_id'], 
                    f"🛑 PROTECCIÓN ACTIVADA\n❌ {stats['pct_perdedoras']:.0f}% pérdidas\n⚠️ Bot en MODO DEMO",
                    self.config, 'proteccion')
    
    def reload_config(self):
        """Recarga la configuración detectando cambios de modo"""
        with self._lock:
            old_modo = self.config.get('modo_demo', True)
            self.config = load_config()
            new_modo = self.config.get('modo_demo', True)
            
            # Detectar cambio manual de modo
            if old_modo != new_modo:
                if not new_modo:  # Cambió a REAL
                    if self.modo_proteccion_activado:
                        self.modo_proteccion_activado = False
                        self._ops_ganadoras_proteccion = 0
                        self.log("🔓 Protección reseteada: usuario cambió manualmente a MODO REAL", "INFO")
                    else:
                        self.log("🟢 Cambio manual a MODO REAL", "INFO")
                    if self.config.get('telegram_bot_token') and self.config.get('telegram_chat_id'):
                        enviar_telegram(self.config['telegram_bot_token'], self.config['telegram_chat_id'],
                            "🟢 Bot cambiado a MODO REAL", self.config, 'modo')
                else:  # Cambió a DEMO
                    self.log("🔴 Cambio manual a MODO DEMO", "INFO")
                    if self.config.get('telegram_bot_token') and self.config.get('telegram_chat_id'):
                        enviar_telegram(self.config['telegram_bot_token'], self.config['telegram_chat_id'],
                            "🔴 Bot cambiado a MODO DEMO", self.config, 'modo')
        self.log("🔄 Configuración recargada", "INFO")
        
        # Reiniciar handler Telegram si hay tokens
        handler = getattr(self, '_telegram_handler', None)
        if handler and not handler._running and self.config.get('telegram_bot_token') and self.config.get('telegram_chat_id'):
            handler.start()
    
    def toggle_modo(self):
        """Cambia entre DEMO y REAL. Retorna el nuevo estado."""
        with self._lock:
            nuevo_modo = not self.config.get('modo_demo', True)
            self.config['modo_demo'] = nuevo_modo
            
            if not nuevo_modo and self.modo_proteccion_activado:
                self.modo_proteccion_activado = False
                self._ops_ganadoras_proteccion = 0
                self.log("🔓 Protección reseteada al cambiar manualmente a REAL", "INFO")
            
            save_config(self.config)
            modo_str = "DEMO" if nuevo_modo else "REAL"
            self.log(f"{'🔴' if nuevo_modo else '🟢'} Modo cambiado a {modo_str}", "SUCCESS")
            
            if self.config.get('telegram_bot_token') and self.config.get('telegram_chat_id'):
                enviar_telegram(self.config['telegram_bot_token'], self.config['telegram_chat_id'],
                    f"{'🔴' if nuevo_modo else '🟢'} Bot cambiado a MODO {modo_str}", self.config, 'modo')
            
            return nuevo_modo
    
    def cerrar_posicion_manual(self, symbol):
        """Cierra una posición manualmente (llamado desde la UI)"""
        with self._lock:
            if symbol in self.open_positions:
                # Actualizar precio antes de cerrar
                posicion = self.open_positions[symbol]
                timeframe = posicion.get('timeframe', '1h')
                try:
                    precio_fresco = self.market.get_current_price(symbol)
                    if precio_fresco > 0:
                        posicion['analysis']['precio_actual'] = precio_fresco
                except:
                    pass
                self._cerrar_posicion(symbol, 'CIERRE_MANUAL', self.config)
                return True
            return False
    
    def cancelar_orden_manual(self, symbol):
        """Cancela una orden pendiente manualmente"""
        with self._lock:
            if symbol in self.ordenes_pendientes:
                if self._eliminar_orden_pendiente(symbol):
                    self.log(f"🗑️ {symbol} - Orden cancelada manualmente", "WARNING")
                    return True
                else:
                    self.log(f"⚠️ {symbol} - No se pudo cancelar en Binance", "WARNING")
                    return False
            return False
    
    def editar_fibonacci(self, symbol, nuevo_p0=None, nuevo_p1=None, es_activa=True):
        """Edita P0 y/o P1 y regenera TODOS los niveles Fibonacci (Entry, TP, SL).
        NO modifica el precio de entrada real ni el precio de compra/venta manual."""
        with self._lock:
            if es_activa:
                if symbol not in self.open_positions:
                    return False
                item = self.open_positions[symbol]
            else:
                if symbol not in self.ordenes_pendientes:
                    return False
                item = self.ordenes_pendientes[symbol]
            
            orig = item.get('valores_originales', {})
            p1_viejo = orig.get('p1', 0)
            p0_viejo = orig.get('p0', 0)
            
            p1 = nuevo_p1 if nuevo_p1 is not None and nuevo_p1 > 0 else p1_viejo
            p0 = nuevo_p0 if nuevo_p0 is not None and nuevo_p0 > 0 else p0_viejo
            
            if p0 <= p1:
                self.log(f"⚠️ {symbol} - P0 debe ser mayor que P1", "WARNING")
                return False
            
            rango = p0 - p1
            
            # Obtener niveles Fib configurados
            config = self.config
            entry_fib = config.get('entry_fib_level', 0.618)
            entry_ajuste = config.get('entry_fib_ajuste', 0)
            tp_fib = config.get('tp_fib_level', 0.382)
            tp_ajuste = config.get('tp_fib_ajuste', 0)
            sl_trigger_fib = config.get('sl_trigger_fib', 0.886)
            sl_trigger_ajuste = config.get('sl_trigger_ajuste', 0)
            sl_rebote_fib = config.get('sl_rebote_fib', 0.786)
            sl_definitivo_fib = config.get('sl_definitivo_fib', 0.95)
            sl_definitivo_ajuste = config.get('sl_definitivo_ajuste', 0.064)
            
            # Recalcular precios
            nueva_entrada = p1 + rango * (1 - (entry_fib + entry_ajuste))
            nuevo_tp = p1 + rango * (1 - (tp_fib + tp_ajuste))
            nuevo_sl_trigger = p1 + rango * (1 - (sl_trigger_fib + sl_trigger_ajuste))
            nuevo_sl_definitivo = p1 + rango * (1 - (sl_definitivo_fib + sl_definitivo_ajuste))
            
            # Actualizar valores originales
            orig['p1'] = p1
            orig['p0'] = p0
            orig['tp'] = nuevo_tp
            orig['sl_trigger'] = nuevo_sl_trigger
            orig['sl_definitivo'] = nuevo_sl_definitivo
            orig['entry_fib'] = entry_fib + entry_ajuste
            orig['tp_fib'] = tp_fib + tp_ajuste
            
            # Actualizar analysis para display
            if 'analysis' in item:
                item['analysis']['punto_1'] = {'price': p1}
                item['analysis']['punto_0'] = {'price': p0}
                item['analysis']['precio_tp'] = nuevo_tp
                item['analysis']['precio_sl_trigger'] = nuevo_sl_trigger
                item['analysis']['precio_sl_definitivo'] = nuevo_sl_definitivo
            
            if not es_activa:
                # Para ordenes pendientes, TAMBIÉN actualizar entrada
                orig['entrada'] = nueva_entrada
                item['precio_entrada'] = nueva_entrada
                if 'analysis' in item:
                    item['analysis']['precio_entrada'] = nueva_entrada
            
            # Resetear escalones (nuevo Fib = nueva referencia)
            item['max_escalon_alcanzado'] = 0
            item['escalon_esperando_rebote'] = False
            item['sl_escalon_info'] = None
            
            beneficio = ((nuevo_tp - (item.get('precio_entrada_real', 0) or nueva_entrada)) / (item.get('precio_entrada_real', 0) or nueva_entrada)) * 100 if (item.get('precio_entrada_real', 0) or nueva_entrada) > 0 else 0
            
            self.log(f"📐 {symbol} - Fibonacci recalculado: P1:{fmt_precio(p1)} → P0:{fmt_precio(p0)} | Entry:{fmt_precio(nueva_entrada)} | TP:{fmt_precio(nuevo_tp)} ({beneficio:+.1f}%) | SL:{fmt_precio(nuevo_sl_definitivo)}", "INFO")
            
            return True

    def editar_precios_pendiente(self, symbol, nuevo_entrada=None, nuevo_tp=None):
        """Edita precios de una orden pendiente. Recalcula SL proporcionalmente."""
        with self._lock:
            if symbol not in self.ordenes_pendientes:
                return False
            
            orden = self.ordenes_pendientes[symbol]
            orig = orden.get('valores_originales', {})
            p1 = orig.get('p1', 0)
            p0 = orig.get('p0', 0)
            rango = p0 - p1 if p0 > p1 else 0
            
            if nuevo_entrada is not None and nuevo_entrada > 0:
                orden['precio_entrada'] = nuevo_entrada
                orig['entrada'] = nuevo_entrada
                if 'analysis' in orden:
                    orden['analysis']['precio_entrada'] = nuevo_entrada
                self.log(f"✏️ {symbol} - Entrada editada → {fmt_precio(nuevo_entrada)}", "INFO")
            
            if nuevo_tp is not None and nuevo_tp > 0:
                orig['tp'] = nuevo_tp
                if 'analysis' in orden:
                    orden['analysis']['precio_tp'] = nuevo_tp
                # Recalcular beneficio esperado
                entrada = orig.get('entrada', orden.get('precio_entrada', 0))
                if entrada > 0:
                    orig['beneficio_pct'] = ((nuevo_tp - entrada) / entrada) * 100
                self.log(f"✏️ {symbol} - TP editado → {fmt_precio(nuevo_tp)}", "INFO")
            
            # Recalcular SL proporcionalmente manteniendo ratios Fib
            if rango > 0:
                sl_trigger_fib = orig.get('sl_trigger_fib', self.config.get('sl_trigger_fib', 0.886))
                sl_definitivo_fib = orig.get('sl_definitivo_fib', self.config.get('sl_definitivo_fib', 0.95))
                orig['sl_trigger'] = p1 + rango * (1 - sl_trigger_fib)
                orig['sl_definitivo'] = p1 + rango * (1 - sl_definitivo_fib)
            
            # MODO REAL: Cancelar y recrear LIMIT BUY
            es_real = not self.config.get('modo_demo', True) and self.orders._is_configured()
            if es_real and orden.get('binance_order_id'):
                self._cancelar_orden_binance_pendiente(symbol, orden)
                self._colocar_limit_buy_binance(symbol, orden, self.config)
            
            return True
    
    def editar_precios_posicion(self, symbol, nuevo_tp=None, nuevo_sl=None):
        """Edita TP/SL de una posición activa. Actualiza OCO en Binance si aplica."""
        with self._lock:
            if symbol not in self.open_positions:
                return False
            
            pos = self.open_positions[symbol]
            orig = pos.get('valores_originales', {})
            
            if nuevo_tp is not None and nuevo_tp > 0:
                orig['tp'] = nuevo_tp
                if 'analysis' in pos:
                    pos['analysis']['precio_tp'] = nuevo_tp
                self.log(f"✏️ {symbol} - TP editado → {fmt_precio(nuevo_tp)}", "INFO")
            
            if nuevo_sl is not None and nuevo_sl > 0:
                orig['sl_definitivo'] = nuevo_sl
                # Ajustar trigger un poco por encima
                orig['sl_trigger'] = nuevo_sl * 1.003
                self.log(f"✏️ {symbol} - SL editado → {fmt_precio(nuevo_sl)}", "INFO")
            
            # MODO REAL: Actualizar OCO en Binance
            es_real = pos.get('modo') == 'REAL' and self.orders._is_configured()
            if es_real and pos.get('binance_oco_id'):
                tp_eff = orig.get('tp', 0)
                sl_trigger_eff = orig.get('sl_trigger', 0)
                sl_def_eff = orig.get('sl_definitivo', 0)
                if tp_eff > 0 and sl_def_eff > 0:
                    self._actualizar_oco_binance(symbol, pos, self.config, tp_eff, sl_trigger_eff, sl_def_eff)
                    pos['oco_tp_vigente'] = tp_eff
                    pos['oco_sl_vigente'] = sl_def_eff
            
            return True
    
    def get_estado(self):
        """Devuelve el estado actual del bot"""
        with self._lock:
            return {
                'running': self.running,
                'paused': self.paused,
                'start_time': self.start_time,
                'open_positions': self.open_positions.copy(),
                'ordenes_pendientes': self.ordenes_pendientes.copy(),
                'oportunidades': self.oportunidades.copy(),
                'last_update': self.last_update,
                'btc_status': self.btc_status.copy() if self.btc_status else {},
                'fase_mercado': self.fase_mercado,
                'estadisticas': self.stats.estadisticas.copy(),
                'cola_espera': self.cola_espera.copy()
            }
    
    def test_conexiones(self):
        """Testea las conexiones a APIs"""
        resultados = {}
        resultados['binance'] = test_binance_connection(
            self.config.get('binance_api_key', ''),
            self.config.get('binance_api_secret', '')
        )
        resultados['telegram'] = test_telegram_connection(
            self.config.get('telegram_bot_token', ''),
            self.config.get('telegram_chat_id', '')
        )
        return resultados
    
    def _run_loop(self):
        """Loop principal del bot"""
        while not self._stop_event.is_set():
            if self.paused:
                time.sleep(1)
                continue
            
            try:
                self._ciclo_trading()
            except Exception as e:
                self.log(f"❌ Error en ciclo: {str(e)}", "ERROR")
            
            # Esperar intervalo configurado
            intervalo = self.config.get('auto_refresh_interval', 30)
            for _ in range(intervalo):
                if self._stop_event.is_set():
                    break
                time.sleep(1)
    
    def _ciclo_trading(self):
        """Un ciclo completo de trading (con análisis escalonado por temporalidad)"""
        with self._lock:
            config = self.config.copy()
        
        # Reset contador de SLs este ciclo (anti-crash)
        self._sl_hits_este_ciclo = 0
        
        # Configurar API keys para órdenes reales
        self.orders.configurar(
            config.get('binance_api_key', ''),
            config.get('binance_api_secret', '')
        )
        
        # Determinar si estamos en modo real
        es_modo_real = not config.get('modo_demo', True) and self.orders._is_configured()
        
        # 0. SINCRONIZACIÓN CON BINANCE
        # Al arrancar (ciclo 0) + cada sync_interval minutos
        sync_interval_min = config.get('sync_interval_minutos', 10)
        sync_interval_ciclos = max(1, int((sync_interval_min * 60) / config.get('auto_refresh_interval', 30)))
        
        forzar_sync = False
        if self._ciclo_contador == 0:
            forzar_sync = True  # Siempre al arrancar
            self.log("🔄 SYNC al arrancar: Consultando Binance antes de operar...", "INFO")
        elif self._ciclo_contador % sync_interval_ciclos == 0:
            forzar_sync = True
        
        if es_modo_real and forzar_sync:
            try:
                self._sincronizar_con_binance(config)
            except Exception as e:
                self.log(f"⚠️ Error en sync: {str(e)}", "WARNING")
        
        # 1. Verificar estado de BTC
        self.btc_status = self.analyzer.detectar_caida_btc()
        self.fase_mercado = self.analyzer.detectar_fase_mercado()
        
        # 2. Protección BTC (solo logear si cambia de nivel)
        if config.get('proteccion_caida_btc', True) and self.btc_status.get('nivel_alerta') != 'NORMAL':
            nivel_actual = self.btc_status.get('nivel_alerta', 'NORMAL')
            if nivel_actual != self._ultimo_nivel_btc_logueado:
                self._ultimo_nivel_btc_logueado = nivel_actual
            self._ejecutar_proteccion_btc(config)
        else:
            if self._ultimo_nivel_btc_logueado is not None and self._ultimo_nivel_btc_logueado != 'NORMAL':
                self.log(f"✅ BTC normalizado (era {self._ultimo_nivel_btc_logueado})", "SUCCESS")
            self._ultimo_nivel_btc_logueado = 'NORMAL'
        
        # 2.5 Protección por pérdidas
        self._ejecutar_proteccion_perdidas(config)
        
        # 3. Monitorear posiciones abiertas (SIEMPRE, cada ciclo)
        self._monitorear_posiciones(config)
        
        # 4. Monitorear órdenes pendientes (SIEMPRE, cada ciclo)
        self._monitorear_ordenes(config)
        
        # 5. Buscar nuevas oportunidades (ESCALONADO por temporalidad)
        # Ciclo 0: 1h, Ciclo 1: 4h, Ciclo 2: 1d, Ciclo 3: todas
        temporalidades_activas = config.get('temporalidades_activas', ['1h', '4h', '1d'])
        
        if self._ciclo_contador % 4 == 3:
            # Cada 4 ciclos: análisis completo de todas las temporalidades
            tf_este_ciclo = temporalidades_activas
        else:
            # Rotar: solo analizar 1 temporalidad por ciclo
            idx = self._ciclo_contador % len(temporalidades_activas)
            tf_este_ciclo = [temporalidades_activas[idx]]
        
        self._buscar_oportunidades(config, tf_este_ciclo)
        
        # 6. Evaluar Swaps Inteligentes
        if config.get('swap_automatico', False) and self.oportunidades:
            swaps_sugeridos = self._evaluar_swaps_inteligentes(config, self.oportunidades)
            if swaps_sugeridos:
                mejor_swap = swaps_sugeridos[0]
                self._ejecutar_swap(mejor_swap, config)
        
        # 7. Rebalanceo de órdenes en Binance (cada 10 ciclos ≈ 5 min)
        es_modo_real = not config.get('modo_demo', True) and self.orders._is_configured()
        if es_modo_real and self._ciclo_contador % 10 == 5:
            self._rebalancear_ordenes_binance(config)

        self.last_update = datetime.utcnow()
        self._ciclo_contador += 1
        # Guardar estado a disco (sobrevive reinicios)
        self._save_state()
        # NO logear "Ciclo completado" - es ruido. La UI muestra last_update
    
    def _ejecutar_proteccion_btc(self, config):
        """Ejecuta protección contra caídas de BTC"""
        nivel = self.btc_status.get('nivel_alerta', 'NORMAL')
        if nivel == 'NORMAL':
            return
        
        # Solo logear si el nivel cambió (evitar spam)
        if nivel != self._ultimo_nivel_btc_logueado:
            caida_1h = self.btc_status.get('caida_1h', 0)
            self.log(f"⚠️ Protección BTC: {nivel} ({caida_1h:+.1f}% 1h)", "WARNING")
        
        with self._lock:
            if nivel == 'SEVERA':
                for symbol in list(self.open_positions.keys()):
                    self._cerrar_posicion(symbol, 'EMERGENCIA_BTC', config)
            elif nivel == 'FUERTE':
                for symbol, pos_data in list(self.open_positions.items()):
                    analysis = pos_data.get('analysis', {})
                    precio_actual = analysis.get('precio_actual', 0)
                    precio_entrada = pos_data.get('precio_entrada_real', 0)
                    if precio_actual < precio_entrada:
                        self._cerrar_posicion(symbol, 'PROTECCION_BTC', config)
    
    def _monitorear_posiciones(self, config):
        """Monitorea posiciones abiertas con sistema de escalones.
        CRÍTICO: Usa valores_originales para P1/P0/TP/SL, análisis fresco SOLO para precio actual.
        CRÍTICO2: Si el análisis falla, IGUALMENTE verificar SL con precio del ticker."""
        with self._lock:
            for symbol, pos_data in list(self.open_positions.items()):
                timeframe_actual = pos_data.get('timeframe', '1h')
                es_pos_real = pos_data.get('modo') == 'REAL' and self.orders._is_configured()
                
                # === REINTENTO VENTA FALLIDA ===
                if pos_data.get('_venta_fallida') and es_pos_real:
                    motivo_orig = pos_data.get('_venta_fallida_motivo', 'TAKE_PROFIT')
                    
                    # Contador de reintentos (max 5)
                    retry_count = pos_data.get('_venta_fallida_retries', 0) + 1
                    pos_data['_venta_fallida_retries'] = retry_count
                    
                    if retry_count > 5:
                        # Demasiados reintentos → abandonar y marcar como dust
                        self.log(f"🗑️ {symbol} - Venta fallida {retry_count}x. Abandonando posición (probablemente dust o tokens locked).", "WARNING")
                        del self.open_positions[symbol]
                        self._save_state()
                        continue
                    
                    self.log(f"🔄 {symbol} - Reintentando venta fallida ({retry_count}/5) (motivo original: {motivo_orig})", "WARNING")
                    cantidad = pos_data.get('cantidad', 0)
                    
                    # Usar balance REAL de Binance (fees reducen la cantidad)
                    quote = config.get('pares_trading', ['USDC'])[0]
                    asset = symbol.replace(quote, '')
                    balances = self.orders.get_all_balances(min_value_usdc=0)
                    if balances and asset in balances:
                        free_bal = balances[asset].get('free', 0)
                        locked_bal = balances[asset].get('locked', 0)
                        
                        # Si tokens están locked (en orden SELL existente), no intentar MARKET SELL
                        if locked_bal > 0 and free_bal < 1.0:
                            self.log(f"⚠️ {symbol} - Tokens locked en orden existente ({locked_bal:.4f} locked, {free_bal:.4f} free). Limpiando posición del bot.", "WARNING")
                            del self.open_positions[symbol]
                            self._save_state()
                            continue
                        
                        if free_bal > 0:
                            cantidad = free_bal
                        else:
                            # Sin balance libre → no hay nada que vender
                            self.log(f"⚠️ {symbol} - Sin balance libre. Limpiando posición.", "WARNING")
                            del self.open_positions[symbol]
                            self._save_state()
                            continue
                    else:
                        # Token no existe en Binance → limpiar
                        self.log(f"⚠️ {symbol} - Token no encontrado en Binance. Limpiando posición.", "WARNING")
                        del self.open_positions[symbol]
                        self._save_state()
                        continue
                    
                    # Verificar NOTIONAL mínimo antes de intentar
                    try:
                        precio_act = self.market.get_current_price(symbol)
                        valor_venta = cantidad * precio_act if precio_act > 0 else 0
                        if valor_venta < 5.0:
                            self.log(f"🗑️ {symbol} - Valor a vender ({valor_venta:.2f} USDC) < mínimo NOTIONAL. Abandonando como dust.", "WARNING")
                            del self.open_positions[symbol]
                            self._save_state()
                            continue
                    except:
                        pass
                    
                    result = self.orders.place_market_sell(symbol, cantidad)
                    if result.get('success'):
                        precio_venta = result.get('avg_price', 0)
                        precio_entrada = pos_data.get('precio_entrada_real', 0)
                        beneficio_pct = ((precio_venta - precio_entrada) / precio_entrada * 100) if precio_entrada > 0 else 0
                        beneficio_usd = (precio_venta - precio_entrada) * cantidad if precio_entrada > 0 else 0
                        
                        emoji = "🟢" if beneficio_pct >= 0 else "🔴"
                        self.log(f"{emoji} VENTA (reintento): {symbol} [REAL] | {beneficio_pct:+.2f}% | {motivo_orig} | @ {fmt_precio(precio_venta)} | ${beneficio_usd:.2f}", "SUCCESS" if beneficio_pct >= 0 else "WARNING")
                        
                        try:
                            self.stats.registrar_operacion(
                                symbol=symbol, fecha_entrada=pos_data.get('fecha_entrada', ''),
                                fecha_salida=datetime.utcnow().isoformat(),
                                precio_entrada=precio_entrada, precio_salida=precio_venta,
                                beneficio_pct=beneficio_pct, beneficio_usd=beneficio_usd,
                                tipo='REAL', p1_suelo=pos_data.get('p1_suelo', 0),
                                p0_maximo=pos_data.get('p0_maximo', 0),
                                temporalidad=timeframe_actual
                            )
                        except:
                            pass
                        
                        if beneficio_pct < 0:
                            self.blacklist.añadir(symbol, precio_entrada, config)
                        
                        del self.open_positions[symbol]
                        self._save_state()
                        continue
                    else:
                        self.log(f"❌ {symbol} - Venta sigue fallando: {result.get('error', '?')}", "ERROR")
                        continue
                
                # === CHECK OCO BINANCE: Si hay OCO y fue ejecutada, registrar resultado ===
                if es_pos_real and pos_data.get('binance_oco_id'):
                    try:
                        oco_status = self.orders.get_oco_status(symbol, pos_data['binance_oco_id'])
                        if oco_status:
                            list_status = oco_status.get('listOrderStatus') or oco_status.get('listStatusType', '')
                            
                            if list_status == 'ALL_DONE':
                                # OCO ejecutada por Binance → determinar si fue TP o SL
                                # Consultar órdenes individuales para saber cuál se ejecutó
                                motivo = 'TAKE_PROFIT'  # Default
                                precio_ejecucion = 0
                                
                                # Intentar obtener info de las sub-órdenes
                                sub_orders = oco_status.get('orderReports', oco_status.get('orders', []))
                                for order_info in sub_orders:
                                    order_id = order_info.get('orderId')
                                    if order_id:
                                        # Consultar cada orden individual
                                        order_detail = self.orders.get_order_status(symbol, order_id)
                                        if order_detail and order_detail.get('status') == 'FILLED':
                                            tipo = order_detail.get('type', '')
                                            precio_ejecucion = float(order_detail.get('price', 0))
                                            if tipo in ('STOP_LOSS_LIMIT', 'STOP_LOSS'):
                                                motivo = 'STOP_LOSS_OCO'
                                            else:
                                                motivo = 'TAKE_PROFIT'
                                            break
                                
                                # Si no pudimos consultar órdenes, inferir por precio
                                if precio_ejecucion <= 0:
                                    try:
                                        precio_actual_check = self.market.get_current_price(symbol)
                                        tp_vigente = pos_data.get('oco_tp_vigente', 0)
                                        sl_vigente = pos_data.get('oco_sl_vigente', 0)
                                        entrada = pos_data.get('precio_entrada_real', 0)
                                        if tp_vigente > 0 and precio_actual_check >= tp_vigente * 0.99:
                                            motivo = 'TAKE_PROFIT'
                                        elif sl_vigente > 0 and precio_actual_check <= sl_vigente * 1.01:
                                            motivo = 'STOP_LOSS_OCO'
                                    except:
                                        pass
                                
                                self.log(f"🏦 {symbol} - OCO ejecutada por Binance ({motivo})", "SUCCESS")
                                self._cerrar_posicion(symbol, motivo, config)
                                continue
                    except Exception as e:
                        self.log(f"⚠️ {symbol} - Error consultando OCO: {str(e)[:80]}", "WARNING")
                
                # === REINTENTAR OCO: Si es REAL sin OCO, intentar colocarla ===
                elif es_pos_real and not pos_data.get('binance_oco_id'):
                    orig_oco = pos_data.get('valores_originales', {})
                    tp_oco = orig_oco.get('tp', 0)
                    cantidad_oco = pos_data.get('cantidad', 0)
                    
                    # Usar SL de escalón si está activo, sino original
                    sl_escalon_info = pos_data.get('sl_escalon_info')
                    if sl_escalon_info and sl_escalon_info.get('proteccion_activa'):
                        sl_trig_oco = sl_escalon_info.get('sl_trigger_precio', 0)
                        sl_def_oco = sl_escalon_info.get('sl_definitivo_precio', 0)
                        if sl_trig_oco <= 0 or sl_def_oco <= 0:
                            sl_def_oco = orig_oco.get('sl_definitivo', 0)
                            sl_trig_oco = orig_oco.get('sl_trigger', sl_def_oco * 1.002)
                        self.log(f"🛡️ {symbol} - OCO con SL escalón: trigger {fmt_precio(sl_trig_oco)} | def {fmt_precio(sl_def_oco)}", "INFO")
                    else:
                        sl_def_oco = orig_oco.get('sl_definitivo', 0)
                        sl_trig_oco = orig_oco.get('sl_trigger', sl_def_oco * 1.002 if sl_def_oco > 0 else 0)
                    
                    # Usar TP magnético/extendido si existe
                    tp_vigente = pos_data.get('oco_tp_vigente', 0)
                    if tp_vigente > 0:
                        tp_oco = tp_vigente
                    
                    if tp_oco > 0 and sl_def_oco > 0 and cantidad_oco > 0:
                        result = self.orders.place_oco_sell(symbol, cantidad_oco, tp_oco, sl_trig_oco, sl_def_oco)
                        if result.get('success'):
                            pos_data['binance_oco_id'] = result['orderListId']
                            pos_data['binance_oco_orders'] = result['orders']
                            pos_data['oco_tp_vigente'] = result['tp_price']
                            pos_data['oco_sl_vigente'] = result['sl_limit']
                            self.log(f"🛡️ {symbol} - OCO SELL colocada (reintento) | TP:{fmt_precio(result['tp_price'])} | SL:{fmt_precio(result['sl_limit'])}", "SUCCESS")
                
                analysis = self.analyzer.analizar_moneda(symbol, config, timeframe_actual, modo_monitoreo=True)
                
                # === VALORES ORIGINALES (siempre disponibles) ===
                orig = pos_data.get('valores_originales', {})
                p1_orig = orig.get('p1', pos_data.get('p1_suelo', 0))
                p0_orig = orig.get('p0', pos_data.get('p0_maximo', 0))
                tp_orig = orig.get('tp', 0)
                sl_trigger_orig = orig.get('sl_trigger', 0)
                sl_definitivo_orig = orig.get('sl_definitivo', 0)
                precio_entrada = pos_data.get('precio_entrada_real', 0)
                
                if analysis['status'] == 'OK':
                    # Guardar análisis fresco para precio actual y display
                    pos_data['analysis'] = analysis
                    precio_actual = analysis['precio_actual']
                    
                    # Fallbacks si valores_originales está vacío
                    if p1_orig == 0:
                        p1_orig = analysis.get('punto_1', {}).get('price', 0)
                    if p0_orig == 0:
                        p0_orig = analysis.get('punto_0', {}).get('price', 0)
                    if tp_orig == 0:
                        tp_orig = analysis.get('precio_tp', 0)
                    if sl_trigger_orig == 0:
                        sl_trigger_orig = analysis.get('precio_sl_trigger', 0)
                    if sl_definitivo_orig == 0:
                        sl_definitivo_orig = analysis.get('precio_sl_definitivo', 0)
                    
                    # Calcular SL de escalón con P1/P0 ORIGINALES
                    sl_escalon = calcular_sl_escalon(pos_data, config, p1_orig, p0_orig)
                    
                    # Guardar escalón info para la UI (barra niveles)
                    if sl_escalon and sl_escalon.get('proteccion_activa'):
                        pos_data['sl_escalon_info'] = sl_escalon
                    else:
                        pos_data['sl_escalon_info'] = None
                    
                    # Log si subió de escalón
                    if pos_data.get('escalon_subio', False):
                        nivel_fib = NIVELES_FIB[pos_data.get('max_escalon_alcanzado', 0)] if pos_data.get('max_escalon_alcanzado', 0) < len(NIVELES_FIB) else 0
                        self.log(f"📈 {symbol} - ESCALÓN +{pos_data.get('max_escalon_alcanzado', 0)} alcanzado (nivel Fib {nivel_fib})", "SUCCESS")
                        if sl_escalon and sl_escalon.get('proteccion_activa'):
                            sl_precio = sl_escalon.get('sl_trigger_precio', 0)
                            self.log(f"   └─ 🛡️ Protección activada: SL subido a {fmt_precio(sl_precio)}", "SUCCESS")
                    
                    # Determinar TP a usar (ORIGINAL, no el fresco)
                    tp_precio = tp_orig
                    
                    # Calcular TP de reentradas (si aplica)
                    tp_reentradas = calcular_tp_reentradas(pos_data, config)
                    if tp_reentradas and config.get('reentradas_progresivas', False):
                        if precio_actual >= tp_orig:
                            tp_precio = tp_reentradas['tp_max_precio']
                            pos_data['reentrada_activa'] = True
                    
                    # === TP DINÁMICO MAGNÉTICO ===
                    # Ajustar TP basándose en resistencias actuales (usa tp_orig como base)
                    if config.get('usar_fib_magnetico', True) and config.get('usar_tp_dinamico', True):
                        tp_mag, tp_mag_info = self.analyzer.calcular_tp_dinamico_magnetico(
                            symbol, pos_data, config, timeframe_actual
                        )
                        if tp_mag is not None:
                            # SEGURIDAD: TP magnético nunca puede ser menor que el precio de entrada
                            if tp_mag > precio_entrada:
                                # SEGURIDAD R:R: No ajustar si destroza el risk/reward
                                ganancia_mag_pct = ((tp_mag - precio_entrada) / precio_entrada) * 100
                                sl_def = orig.get('precio_sl_definitivo', sl_definitivo_orig)
                                riesgo_pct = ((precio_entrada - sl_def) / precio_entrada) * 100 if sl_def > 0 and precio_entrada > 0 else 0
                                min_rr = config.get('min_risk_reward', 1.0)
                                
                                rr_ok = True
                                if riesgo_pct > 0:
                                    rr_nuevo = ganancia_mag_pct / riesgo_pct
                                    if rr_nuevo < min_rr:
                                        rr_ok = False
                                        # Solo logear una vez
                                        if not pos_data.get('_rr_mag_warned'):
                                            self.log(f"⚠️ {symbol} - TP magnético {fmt_precio(tp_mag)} rechazado: R:R {rr_nuevo:.2f}:1 < {min_rr}:1 (Gan:{ganancia_mag_pct:.1f}% vs Riesgo:{riesgo_pct:.1f}%)", "WARNING")
                                            pos_data['_rr_mag_warned'] = True
                                
                                if rr_ok:
                                    tp_anterior = tp_precio
                                    tp_precio = tp_mag
                                    tipo_ajuste = tp_mag_info.get('tipo', '')
                                    
                                    if tipo_ajuste == 'RESISTENCIA_INTERMEDIA':
                                        last_tp_mag = pos_data.get('last_tp_magnetico', 0)
                                        if abs(tp_mag - last_tp_mag) / tp_mag > 0.003:
                                            fuerza = tp_mag_info.get('resistencia_fuerza', 0)
                                            benef = tp_mag_info.get('beneficio_nuevo_pct', 0)
                                            self.log(f"🧲 {symbol} - TP ajustado: {fmt_precio(tp_anterior)} → {fmt_precio(tp_mag)} | Resistencia fuerza:{fuerza:.0f} | +{benef:.1f}%", "INFO")
                                            pos_data['last_tp_magnetico'] = tp_mag
                                            pos_data['tp_mag_info'] = tp_mag_info
                                    
                                    elif tipo_ajuste == 'TP_EXTENDIDO':
                                        last_tp_ext = pos_data.get('last_tp_extendido', 0)
                                        if abs(tp_mag - last_tp_ext) / tp_mag > 0.003:
                                            ext_pct = tp_mag_info.get('extension_pct', 0)
                                            benef = tp_mag_info.get('beneficio_extendido_pct', 0)
                                            self.log(f"🚀 {symbol} - TP extendido: {fmt_precio(tp_anterior)} → {fmt_precio(tp_mag)} (+{ext_pct:.1f}%) | +{benef:.1f}% beneficio", "SUCCESS")
                                            pos_data['last_tp_extendido'] = tp_mag
                                            pos_data['tp_mag_info'] = tp_mag_info
                    
                    # Verificar TP
                    if precio_actual >= tp_precio:
                        motivo = 'TAKE_PROFIT_REENTRADA' if pos_data.get('reentrada_activa') else 'TAKE_PROFIT'
                        self._cerrar_posicion(symbol, motivo, config)
                        continue
                    
                    # === ACTUALIZAR OCO EN BINANCE si niveles cambiaron ===
                    if es_pos_real and pos_data.get('binance_oco_id'):
                        oco_tp_actual = pos_data.get('oco_tp_vigente', 0)
                        oco_sl_actual = pos_data.get('oco_sl_vigente', 0)
                        
                        # Determinar SL efectivo
                        if sl_escalon and sl_escalon.get('proteccion_activa'):
                            sl_efectivo = sl_escalon.get('sl_trigger_precio', sl_definitivo_orig)
                            sl_def_efectivo = sl_escalon.get('sl_definitivo_precio', sl_definitivo_orig)
                        else:
                            sl_efectivo = sl_trigger_orig
                            sl_def_efectivo = sl_definitivo_orig
                        
                        # Si TP o SL cambió significativamente (>0.3%), actualizar OCO
                        tp_cambio = abs(tp_precio - oco_tp_actual) / tp_precio if tp_precio > 0 else 0
                        sl_cambio = abs(sl_def_efectivo - oco_sl_actual) / sl_def_efectivo if sl_def_efectivo > 0 else 0
                        
                        if (tp_cambio > 0.003 or sl_cambio > 0.003) and tp_precio > 0 and sl_def_efectivo > 0:
                            self._actualizar_oco_binance(symbol, pos_data, config, tp_precio, sl_efectivo, sl_def_efectivo)
                            pos_data['oco_tp_vigente'] = tp_precio
                            pos_data['oco_sl_vigente'] = sl_def_efectivo
                    
                    # Verificar SL (usar escalón si está activo, sino normal con valores ORIGINALES)
                    if sl_escalon and sl_escalon.get('proteccion_activa'):
                        estado_sl = self._evaluar_sl_escalon(pos_data, sl_escalon, config)
                        if estado_sl.get('accion'):
                            self._cerrar_posicion(symbol, estado_sl['estado'], config)
                    else:
                        estado_sl = evaluar_stop_loss_dinamico(pos_data, config, sl_trigger_orig, sl_definitivo_orig)
                        if estado_sl['accion']:
                            self._cerrar_posicion(symbol, estado_sl['estado'], config)
                
                else:
                    # ============================================================
                    # ANÁLISIS FALLÓ - pero DEBEMOS verificar TP y SL de emergencia
                    # Sin esto, un TP puede perderse o un crash pasar desapercibido
                    # ============================================================
                    try:
                        df_precio = self.market.get_klines_data(symbol, '1m', 1)
                        if not df_precio.empty:
                            precio_actual = df_precio['close'].iloc[-1]
                            # Actualizar precio en analysis existente para la UI
                            if 'analysis' in pos_data:
                                pos_data['analysis']['precio_actual'] = precio_actual
                            
                            ganancia_pct = ((precio_actual - precio_entrada) / precio_entrada * 100) if precio_entrada > 0 else 0
                            
                            # TP DE EMERGENCIA: si el precio supera el TP original → vender
                            if tp_orig > 0 and precio_actual >= tp_orig:
                                self.log(f"💰 {symbol} - TP EMERGENCIA: Precio {fmt_precio(precio_actual)} >= TP {fmt_precio(tp_orig)} | +{ganancia_pct:.1f}% | Análisis falló pero TP activo", "SUCCESS")
                                self._cerrar_posicion(symbol, 'TAKE_PROFIT', config)
                                continue
                            
                            perdida_pct = ganancia_pct
                            
                            # SL DEFINITIVO DE EMERGENCIA: si el precio está por debajo del SL definitivo → vender YA
                            if sl_definitivo_orig > 0 and precio_actual <= sl_definitivo_orig:
                                self.log(f"🚨 {symbol} - SL EMERGENCIA: Precio {fmt_precio(precio_actual)} <= SL Definitivo {fmt_precio(sl_definitivo_orig)} | {perdida_pct:.1f}% | Análisis falló pero SL activo", "ERROR")
                                self._cerrar_posicion(symbol, 'SL_EMERGENCIA', config)
                                continue
                            
                            # SL TRIGGER: activar espera de rebote
                            if sl_trigger_orig > 0 and precio_actual <= sl_trigger_orig:
                                # Usar la misma lógica que evaluar_stop_loss_dinamico
                                estado_sl = evaluar_stop_loss_dinamico(pos_data, config, sl_trigger_orig, sl_definitivo_orig)
                                if estado_sl['accion']:
                                    self.log(f"🚨 {symbol} - SL EMERGENCIA ({estado_sl['estado']}): Precio {fmt_precio(precio_actual)} | {perdida_pct:.1f}% | Análisis falló pero SL activo", "ERROR")
                                    self._cerrar_posicion(symbol, estado_sl['estado'], config)
                                    continue
                            
                            # SL PORCENTAJE MÁXIMO: protección absoluta si nada de lo anterior funciona
                            max_perdida = config.get('max_perdida_emergencia_pct', -15.0)
                            if perdida_pct <= max_perdida:
                                self.log(f"🚨 {symbol} - SL EMERGENCIA MÁXIMO: {perdida_pct:.1f}% >= límite {max_perdida}% | Precio {fmt_precio(precio_actual)} | Venta forzada", "ERROR")
                                self._cerrar_posicion(symbol, 'SL_EMERGENCIA_MAX', config)
                                continue
                                
                    except Exception as e:
                        self.log(f"⚠️ {symbol} - Error obteniendo precio de emergencia: {e}", "WARNING")
    
    def _evaluar_sl_escalon(self, posicion, sl_escalon, config):
        """Evalúa SL de escalón con la misma lógica de trigger-rebote-definitivo"""
        analysis = posicion.get('analysis', {})
        precio_actual = analysis.get('precio_actual', 0)
        precio_entrada = posicion.get('precio_entrada_real', 0)
        
        estado = {
            'estado': 'PROTECCION_ESCALON',
            'ganancia_actual': ((precio_actual - precio_entrada) / precio_entrada) * 100 if precio_entrada > 0 else 0,
            'escalon': sl_escalon.get('max_escalon', 0),
            'accion': None
        }
        
        # Si el precio baja del trigger de escalón
        if precio_actual <= sl_escalon['sl_trigger_precio']:
            if posicion.get('escalon_esperando_rebote', False):
                velas_esperadas = posicion.get('escalon_velas_esperadas', 0) + 1
                posicion['escalon_velas_esperadas'] = velas_esperadas
                
                # Si rebota al nivel de rebote
                if precio_actual >= sl_escalon['sl_rebote_precio']:
                    estado.update({
                        'estado': 'ESCALON_REBOTE_EXITOSO',
                        'accion': 'VENDER',
                        'precio_venta': sl_escalon['sl_rebote_precio']
                    })
                    return estado
                
                # Si no rebota en N velas, vender en definitivo
                timeout = config.get('sl_timeout_candles', 5)
                if velas_esperadas >= timeout:
                    estado.update({
                        'estado': 'ESCALON_SL_DEFINITIVO',
                        'accion': 'VENDER',
                        'precio_venta': sl_escalon['sl_definitivo_precio']
                    })
                    return estado
                
                estado.update({
                    'estado': 'ESCALON_ESPERANDO_REBOTE',
                    'velas_restantes': timeout - velas_esperadas
                })
            else:
                # Activar espera de rebote
                posicion['escalon_esperando_rebote'] = True
                posicion['escalon_velas_esperadas'] = 0
                estado.update({
                    'estado': 'ESCALON_TRIGGER_ACTIVADO',
                    'precio_rebote_objetivo': sl_escalon['sl_rebote_precio']
                })
        else:
            # Precio por encima del trigger, resetear
            posicion['escalon_esperando_rebote'] = False
            posicion['escalon_velas_esperadas'] = 0
        
        return estado
    
    def _monitorear_ordenes(self, config):
        """Monitorea órdenes pendientes.
        DEMO: vigila precio y compra cuando llega a entrada.
        REAL: monitorea LIMIT BUY en Binance + detecta fill."""
        es_modo_real = not config.get('modo_demo', True) and self.orders._is_configured()
        
        # ANTI-CRASH: Si saltaron SLs este ciclo, bloquear compras nuevas
        bloquear_compras = self._sl_hits_este_ciclo >= 2
        if bloquear_compras:
            if not hasattr(self, '_crash_guard_logged') or not self._crash_guard_logged:
                self.log(f"🛡️ ANTI-CRASH: {self._sl_hits_este_ciclo} SLs saltaron este ciclo → bloqueando compras nuevas", "WARNING")
                self._crash_guard_logged = True
        else:
            self._crash_guard_logged = False
        
        with self._lock:
            for symbol, orden in list(self.ordenes_pendientes.items()):
                timeframe = orden.get('timeframe', '1h')
                
                # PASO 1: Obtener precio actual rápido
                try:
                    precio_actual_rapido = self.market.get_current_price(symbol)
                except:
                    precio_actual_rapido = 0
                
                # PASO 1.5 (REAL): Verificar si hay LIMIT BUY en Binance pendiente
                if es_modo_real and orden.get('binance_order_id'):
                    try:
                        status = self.orders.get_order_status(symbol, orden['binance_order_id'])
                        if status and status.get('status') == 'FILLED':
                            # ¡COMPRA EJECUTADA POR BINANCE!
                            fill_price = float(status.get('price', 0))
                            fill_qty = float(status.get('executedQty', 0))
                            if fill_price <= 0:
                                # Calcular desde cummulativeQuoteQty
                                cumm_quote = float(status.get('cummulativeQuoteQty', 0))
                                if fill_qty > 0 and cumm_quote > 0:
                                    fill_price = cumm_quote / fill_qty
                            
                            self.log(f"⚡ {symbol} - LIMIT BUY ejecutada en Binance @ {fmt_precio(fill_price)} | Qty: {fill_qty:.6f}", "SUCCESS")
                            self._registrar_compra_y_poner_oco(symbol, orden, config, fill_price, fill_qty)
                            continue
                        
                        elif status and status.get('status') == 'CANCELED':
                            # Orden cancelada externamente (manualmente en Binance)
                            self.log(f"⚠️ {symbol} - LIMIT BUY cancelada externamente en Binance", "WARNING")
                            self._eliminar_orden_pendiente(symbol)
                            self._promover_siguiente_cola(config)
                            continue
                        
                        # Si está NEW o PARTIALLY_FILLED, seguir monitoreando (agotada/P0 checks abajo)
                    except Exception as e:
                        self.log(f"⚠️ {symbol} - Error consultando orden Binance: {str(e)}", "WARNING")
                
                # PASO 1.6 (REAL): Si estamos en REAL pero la orden NO tiene binance_order_id
                # Reintentar a menos que sea un error permanente (formato, símbolo inválido)
                elif es_modo_real and not orden.get('binance_order_id'):
                    if orden.get('binance_placement_failed'):
                        pass  # Error permanente (formato/símbolo), no reintentar
                    else:
                        self._colocar_limit_buy_binance(symbol, orden, config)
                
                # PASO 2: Usar precio de entrada ALMACENADO (no recalcular)
                precio_entrada_original = orden.get('precio_entrada', 0)
                
                # PASO 3 (DEMO): Si precio está cerca o debajo de entrada → comprar
                if not es_modo_real:
                    if bloquear_compras:
                        continue  # Anti-crash: no comprar durante crash
                    if precio_actual_rapido > 0 and precio_entrada_original > 0:
                        if precio_actual_rapido <= precio_entrada_original:
                            # VALIDACIÓN P1: No comprar si el precio perforó P1 (estructura rota)
                            orig_compra = orden.get('valores_originales', {})
                            p1_compra = orig_compra.get('p1', 0)
                            if p1_compra > 0 and precio_actual_rapido < p1_compra * 0.99:
                                p0_compra = orig_compra.get('p0', 0)
                                pct_bajo_p1 = ((precio_actual_rapido - p1_compra) / p1_compra) * 100
                                self.log(f"🚫 {symbol} - Precio {fmt_precio(precio_actual_rapido)} perforó P1 {fmt_precio(p1_compra)} ({pct_bajo_p1:.1f}%) → estructura rota, cancelando orden", "WARNING")
                                if symbol in self.ordenes_pendientes:
                                    self._eliminar_orden_pendiente(symbol)
                                self._promover_siguiente_cola(config)
                                continue
                            
                            if 'analysis' in orden:
                                orden['analysis']['precio_actual'] = precio_actual_rapido
                            
                            self.log(f"⚡ {symbol} - Precio {fmt_precio(precio_actual_rapido)} alcanzó entrada {fmt_precio(precio_entrada_original)} → ejecutando compra", "SUCCESS")
                            compra_ok = self._ejecutar_compra(symbol, orden, config)
                            
                            if compra_ok:
                                continue
                            else:
                                self.log(f"⚠️ {symbol} - Compra falló, cancelando orden para evitar bucle", "WARNING")
                                if symbol in self.ordenes_pendientes:
                                    self._eliminar_orden_pendiente(symbol)
                                self._promover_siguiente_cola(config)
                                continue
                
                # PASO 4: Verificar si el precio superó el P0 original → estructura rota
                orig = orden.get('valores_originales', {})
                p0_original = orig.get('p0', 0)
                if p0_original > 0 and precio_actual_rapido > 0:
                    if precio_actual_rapido > p0_original * 1.01:
                        # Cancelar orden Binance si existe
                        if es_modo_real and orden.get('binance_order_id'):
                            self._cancelar_orden_binance_pendiente(symbol, orden)
                        
                        p1_ag = orig.get('p1', 0)
                        precio_ent_ag = orig.get('entrada', orden.get('precio_entrada', 0))
                        patron_ag = orig.get('patron', '')
                        score_ag = orig.get('score', orden.get('score', 0))
                        patron_tag = f" | 🔍{patron_ag}" if patron_ag and patron_ag not in ('DESCONOCIDO', '') else ""
                        pct_sobre_p0 = ((precio_actual_rapido - p0_original) / p0_original) * 100
                        self.log(f"🔄 {symbol} | {timeframe} | Score:{score_ag:.0f} | P1:{fmt_precio(p1_ag)} → P0:{fmt_precio(p0_original)} | Entr:{fmt_precio(precio_ent_ag)} | Actual:{fmt_precio(precio_actual_rapido)}{patron_tag} | ❌ Precio superó P0 original (+{pct_sobre_p0:.1f}%), estructura cambió", "WARNING")
                        self._eliminar_orden_pendiente(symbol)
                        self._promover_siguiente_cola(config)
                        continue
                
                # PASO 5: Hacer análisis periódico (para detectar agotadas y cancelar)
                try:
                    analysis = self.analyzer.analizar_moneda(symbol, config, timeframe, modo_monitoreo=True)
                except Exception as e:
                    continue
                
                # Si la moneda se volvió agotada, cancelar orden
                if analysis.get('moneda_agotada', False):
                    # Cancelar orden Binance si existe
                    if es_modo_real and orden.get('binance_order_id'):
                        self._cancelar_orden_binance_pendiente(symbol, orden)
                    
                    detalles = analysis.get('detalles_agotada', {})
                    razon = detalles.get('razon', 'Sin detalle')
                    orig = orden.get('valores_originales', {})
                    p1_ag = orig.get('p1', 0)
                    p0_ag = orig.get('p0', 0)
                    precio_ent_ag = orig.get('entrada', orden.get('precio_entrada', 0))
                    precio_actual_ag = detalles.get('precio_actual', 0)  # Algunos detalles lo traen
                    if precio_actual_ag == 0:
                        # Intentar del analysis anterior guardado en la orden
                        precio_actual_ag = orden.get('analysis', {}).get('precio_actual', 0)
                    patron_ag = orig.get('patron', '')
                    score_ag = orig.get('score', orden.get('score', 0))
                    patron_tag = f" | 🔍{patron_ag}" if patron_ag and patron_ag not in ('DESCONOCIDO', '') else ""
                    self.log(f"🔄 {symbol} | {timeframe} | Score:{score_ag:.0f} | P1:{fmt_precio(p1_ag)} → P0:{fmt_precio(p0_ag)} | Entr:{fmt_precio(precio_ent_ag)} | Actual:{fmt_precio(precio_actual_ag)}{patron_tag} | ❌ {razon}", "WARNING")
                    # Debug: mostrar todos los valores que calculó verificar_moneda_agotada
                    caso = detalles.get('caso', '?')
                    self.log(f"   └─ 🔬 DEBUG AGOTADA Caso:{caso} | P1:{fmt_precio(detalles.get('p1', 0))} P0:{fmt_precio(detalles.get('p0', 0))} Rango:{fmt_precio(detalles.get('rango', 0))} | NivelCasiCompra:{fmt_precio(detalles.get('precio_casi_compra', 0))} NivelRebote:{fmt_precio(detalles.get('precio_rebote', 0))} NivelEntrada:{fmt_precio(detalles.get('precio_entrada_real', 0))} | BajoMin:{fmt_precio(detalles.get('bajo_minimo_post_p0', 0))} AltoMax:{fmt_precio(detalles.get('alto_maximo_post_p0', 0))} | AltoRebPostEnt:{fmt_precio(detalles.get('alto_rebote_post_entrada', 0))} AltoRebPostCasi:{fmt_precio(detalles.get('alto_rebote_post_casi_compra', 0))} | Velas:{detalles.get('velas_post_p0', 0)}", "INFO")
                    self._eliminar_orden_pendiente(symbol)
                    self._promover_siguiente_cola(config)
                    continue
                
                if analysis['status'] == 'OK':
                    # Actualizar analysis para UI (precio actual, indicadores frescos)
                    # pero PRESERVAR valores_originales
                    orden['analysis'] = analysis
                    
                    # Verificar cancelación por rebote
                    if config.get('cancelar_orden_rebote', False):
                        nivel_cancelacion = config.get('nivel_rebote_base', 0.382) + config.get('ajuste_rebote', 0.0)
                        precio_cancelacion = analysis['punto_1']['price'] + (analysis['rango'] * (1 - nivel_cancelacion))
                        if analysis['precio_actual'] >= precio_cancelacion:
                            self.log(f"🚫 {symbol} - CANCELADA: Rebotó demasiado ({fmt_precio(analysis['precio_actual'])} >= {fmt_precio(precio_cancelacion)})", "WARNING")
                            self._eliminar_orden_pendiente(symbol)
                            self._promover_siguiente_cola(config)
    
    def _promover_siguiente_cola(self, config):
        """Promueve la siguiente moneda de la cola de espera a orden pendiente"""
        if not self.cola_espera:
            return
        
        # CHECK MAX ORDENES: No promover si ya estamos al límite
        max_pos = config.get('max_positions', 5)
        total_activas = len(self.open_positions) + len(self.ordenes_pendientes)
        if total_activas >= max_pos:
            return
        
        siguiente = self.cola_espera.pop(0)
        symbol = siguiente['symbol']
        timeframe = siguiente['timeframe']
        
        analysis = self.analyzer.analizar_moneda(symbol, config, timeframe)
        if analysis['status'] == 'OK' and not analysis.get('moneda_agotada', False):
            # VALIDACIÓN: No crear orden si el precio ya está por debajo de entrada
            precio_actual = analysis.get('precio_actual', 0)
            precio_entrada = analysis.get('precio_entrada', 0)
            if precio_actual < precio_entrada:
                p1_pr = analysis.get('punto_1', {}).get('price', 0)
                p0_pr = analysis.get('punto_0', {}).get('price', 0)
                self.log(f"⏭️ {symbol} | {timeframe} | P1:{fmt_precio(p1_pr)} → P0:{fmt_precio(p0_pr)} | Entr:{fmt_precio(precio_entrada)} | Actual:{fmt_precio(precio_actual)} | ❌ Precio < entrada al promover", "WARNING")
                return  # No promover, ya pasó la oportunidad
            
            # CANCELAR orden Binance existente si la hay (evitar duplicados)
            self._cancelar_orden_binance_si_existe(symbol, config)
            
            self.ordenes_pendientes[symbol] = {
                'symbol': symbol,
                'timeframe': timeframe,
                'analysis': analysis,
                'score': siguiente.get('score', 0),
                'timestamp_creacion': datetime.utcnow(),
                'precio_entrada': analysis['precio_entrada'],
                'valores_originales': {
                    'p1': analysis.get('punto_1', {}).get('price', 0),
                    'p0': analysis.get('punto_0', {}).get('price', 0),
                    'p1_time': analysis.get('punto_1', {}).get('time'),
                    'p0_time': analysis.get('punto_0', {}).get('time'),
                    'entrada': analysis.get('precio_entrada', 0),
                    'tp': analysis.get('precio_tp', 0),
                    'sl_trigger': analysis.get('precio_sl_trigger', 0),
                    'sl_definitivo': analysis.get('precio_sl_definitivo', 0),
                    'beneficio_pct': analysis.get('beneficio_esperado_pct', 0),
                    'patron': analysis.get('patron_recuperacion', ''),
                    'score': siguiente.get('score', 0),
                    'entry_fib': analysis.get('entry_level_usado', config.get('entry_fib_level', 0.618)),
                    'tp_fib': analysis.get('tp_level_usado', config.get('tp_fib_level', 0.382)),
                    'sl_trigger_fib': config.get('sl_trigger_fib', 0.886),
                    'sl_rebote_fib': config.get('sl_rebote_fib', 0.786),
                    'sl_definitivo_fib': config.get('sl_definitivo_fib', 0.95),
                }
            }
            
            # MODO REAL: Colocar LIMIT BUY en Binance
            if not config.get('modo_demo', True) and self.orders._is_configured():
                self._colocar_limit_buy_binance(symbol, self.ordenes_pendientes[symbol], config)
            
            self.log(f"📥 {symbol} | {timeframe} | Score:{siguiente.get('score', 0):.0f} | P1:{fmt_precio(analysis.get('punto_1', {}).get('price', 0))} → P0:{fmt_precio(analysis.get('punto_0', {}).get('price', 0))} | Entr:{fmt_precio(precio_entrada)} | TP:{fmt_precio(analysis.get('precio_tp', 0))} | promovida de cola", "INFO")
    
    def _buscar_oportunidades(self, config, temporalidades_ciclo=None):
        """Busca nuevas oportunidades de trading (acepta temporalidades específicas para ciclo escalonado)"""
        # ANTI-CRASH: No buscar si saltaron SLs este ciclo
        if self._sl_hits_este_ciclo >= 2:
            return
        
        pair_suffix = config.get('pares_trading', ['USDC'])[0]
        num_analizar = config.get('num_monedas_analizar', 50)
        min_volumen = config.get('min_volumen_24h', 100000)
        
        top_pairs = self.market.get_top_volume_pairs(pair_suffix, num_analizar, min_volumen)
        if top_pairs.empty:
            return
        
        nuevas_oportunidades = []
        temporalidades = temporalidades_ciclo or config.get('temporalidades_activas', ['1h', '4h', '1d'])
        estrategia = config.get('estrategia_scoring', 'C')
        
        for _, row in top_pairs.iterrows():
            symbol = row['symbol']
            
            # Filtrar monedas excluidas
            monedas_excluidas = config.get('monedas_excluidas', [])
            if symbol in monedas_excluidas:
                continue
            
            # Verificar blacklist (pero NO excluir si está en posiciones/órdenes)
            precio_actual = float(row['lastPrice'])
            if self.blacklist.verificar(symbol, precio_actual, config):
                continue
            
            for tf in temporalidades:
                analysis = self.analyzer.analizar_moneda(symbol, config, tf)
                
                if analysis['status'] == 'OK' and not analysis.get('moneda_agotada', False):
                    # FILTRO: No crear orden si el precio ya está significativamente por debajo de entrada
                    # Tolerancia 0.3%: precio justo en la entrada sigue siendo válido
                    margen_opp = analysis['precio_entrada'] * 0.003
                    if analysis['precio_actual'] < (analysis['precio_entrada'] - margen_opp):
                        continue
                    
                    score, detalles = self.analyzer.calcular_score(symbol, top_pairs, analysis, estrategia, config)
                    
                    # Verificar score mínimo por temporalidad
                    min_score_key = f'min_score_{tf}'
                    min_score = config.get(min_score_key, config.get('min_score_compra', 60))
                    
                    if score >= min_score and analysis['beneficio_esperado_pct'] >= config.get('min_beneficio_pct', 0.5):
                        # Obtener subida 24h directamente de los datos de Binance
                        row_moneda = top_pairs[top_pairs['symbol'] == symbol]
                        subida_24h = float(row_moneda['priceChangePercent'].values[0]) if not row_moneda.empty else 0
                        
                        nuevas_oportunidades.append({
                            'symbol': symbol,
                            'timeframe': tf,
                            'score': score,
                            'subida_24h': subida_24h,
                            'detalles_score': detalles,
                            'analysis': analysis,
                            'timestamp': datetime.utcnow()
                        })
        
        with self._lock:
            # MEJORADO: En ciclo escalonado, mezclar con oportunidades existentes de otros timeframes
            if temporalidades_ciclo and len(temporalidades_ciclo) < len(config.get('temporalidades_activas', ['1h', '4h', '1d'])):
                # Mantener oportunidades de temporalidades NO analizadas en este ciclo
                oportunidades_conservadas = [op for op in self.oportunidades if op['timeframe'] not in temporalidades_ciclo]
                todas = oportunidades_conservadas + nuevas_oportunidades
            else:
                todas = nuevas_oportunidades
            
            # Deduplicar por symbol (mantener la de mayor score)
            por_symbol = {}
            for op in todas:
                sym = op['symbol']
                if sym not in por_symbol or op['score'] > por_symbol[sym]['score']:
                    por_symbol[sym] = op
            todas = list(por_symbol.values())
            
            # Ordenar según criterio configurado
            criterio = config.get('criterio_ordenamiento', 'score')
            if criterio == 'subida':
                todas.sort(key=lambda x: x.get('subida_24h', 0), reverse=True)
            else:
                todas.sort(key=lambda x: x['score'], reverse=True)
            
            self.oportunidades = todas[:config.get('max_oportunidades_mostrar', 100)]
            
            # Agregar a órdenes pendientes si hay espacio
            max_pos = config.get('max_positions', 5)
            total_activas = len(self.open_positions) + len(self.ordenes_pendientes)
            
            for op in nuevas_oportunidades:
                if total_activas >= max_pos:
                    # Slots llenos: ¿hay alguna orden PENDIENTE con score mucho peor?
                    # (Solo reemplazar pendientes, NUNCA posiciones ya compradas)
                    if not config.get('upgrade_ordenes_activo', True):
                        if op not in self.cola_espera:
                            self.cola_espera.append(op)
                        continue
                    
                    nuevo_score = op['score']
                    symbol_nuevo = op['symbol']
                    
                    if symbol_nuevo in self.ordenes_pendientes or symbol_nuevo in self.open_positions:
                        continue  # Ya existe
                    
                    # Buscar la orden pendiente con peor score
                    peor_symbol = None
                    peor_score = float('inf')
                    for sym_p, ord_p in self.ordenes_pendientes.items():
                        score_p = ord_p.get('score', 0)
                        if score_p < peor_score:
                            peor_score = score_p
                            peor_symbol = sym_p
                    
                    # Reemplazar si la nueva tiene al menos 10 puntos más de score
                    min_diff = config.get('upgrade_min_score_diff', 10)
                    if peor_symbol and (nuevo_score - peor_score) >= min_diff:
                        # Cancelar orden en Binance y eliminar
                        if not self._eliminar_orden_pendiente(peor_symbol):
                            # No se pudo cancelar en Binance → no hacer upgrade
                            if op not in self.cola_espera:
                                self.cola_espera.append(op)
                            continue
                        self.log(f"🔄 UPGRADE: {peor_symbol} (Score:{peor_score:.0f}) → {symbol_nuevo} (Score:{nuevo_score:.0f}) | +{nuevo_score - peor_score:.0f} puntos", "SUCCESS")
                        # Notificar upgrade por Telegram
                        if config.get('telegram_bot_token') and config.get('telegram_chat_id'):
                            enviar_telegram(config['telegram_bot_token'], config['telegram_chat_id'],
                                f"🔄 UPGRADE\n❌ {peor_symbol} (Score:{peor_score:.0f})\n✅ {symbol_nuevo} (Score:{nuevo_score:.0f})\n📈 +{nuevo_score - peor_score:.0f} puntos",
                                config, 'upgrade')
                        # No break, dejar que caiga al código de creación de orden abajo
                        total_activas -= 1
                    else:
                        # No hay candidato para reemplazar, a la cola
                        if op not in self.cola_espera:
                            self.cola_espera.append(op)
                        continue
                
                symbol = op['symbol']
                if symbol not in self.ordenes_pendientes and symbol not in self.open_positions:
                    # VALIDACIÓN: No crear orden si el precio ya está significativamente por debajo de entrada
                    # Tolerancia 0.3%: precio justo en la entrada sigue siendo válido
                    precio_actual = op['analysis'].get('precio_actual', 0)
                    precio_entrada = op['analysis'].get('precio_entrada', 0)
                    margen_ord = precio_entrada * 0.003
                    if precio_actual < (precio_entrada - margen_ord):
                        # Cooldown: solo logear agotada cada 10 minutos por moneda+timeframe
                        cooldown_key = f"{symbol}_{op['timeframe']}"
                        ahora = datetime.utcnow()
                        ultimo_log = self._agotada_cooldown.get(cooldown_key)
                        
                        if ultimo_log is None or (ahora - ultimo_log).total_seconds() >= 600:
                            p1_ag = op['analysis'].get('punto_1', {}).get('price', 0)
                            p0_ag = op['analysis'].get('punto_0', {}).get('price', 0)
                            patron_ag = op['analysis'].get('patron_recuperacion', '')
                            entry_lvl_ag = op['analysis'].get('entry_level_usado', 0)
                            mag_info = op['analysis'].get('p0p1_magnetico', {})
                            mag_text = ""
                            if mag_info.get('p1_movido') or mag_info.get('p0_movido'):
                                orig_p1 = mag_info.get('p1_original', 0)
                                orig_p0 = mag_info.get('p0_original', 0)
                                mag_text = f" | 🧲MAG(P1:{fmt_precio(orig_p1)}→{fmt_precio(p1_ag)} P0:{fmt_precio(orig_p0)}→{fmt_precio(p0_ag)} rango-{mag_info.get('rango_reducido_pct', 0):.0f}%)"
                            self.log(f"⏭️ {symbol} | {op['timeframe']} - Oportunidad agotada | Entr:{fmt_precio(precio_entrada)} | Actual:{fmt_precio(precio_actual)} | 🔍{patron_ag} Fib:{entry_lvl_ag}{mag_text}", "WARNING")
                            self._agotada_cooldown[cooldown_key] = ahora
                        continue  # No crear orden, buscar siguiente oportunidad
                    
                    # Extraer datos para log detallado
                    analysis = op['analysis']
                    p1 = analysis.get('punto_1', {}).get('price', 0)
                    p0 = analysis.get('punto_0', {}).get('price', 0)
                    precio_tp = analysis.get('precio_tp', 0)
                    beneficio_esp = analysis.get('beneficio_esperado_pct', 0)
                    patron = analysis.get('patron_recuperacion', '')
                    entry_lvl = analysis.get('entry_level_usado', 0)
                    tp_lvl = analysis.get('tp_level_usado', 0)
                    
                    self.ordenes_pendientes[symbol] = {
                        'symbol': symbol,
                        'timeframe': op['timeframe'],
                        'analysis': op['analysis'],
                        'score': op['score'],
                        'detalles_score': op['detalles_score'],
                        'timestamp_creacion': datetime.utcnow(),
                        'precio_entrada': op['analysis']['precio_entrada'],
                        'valores_originales': {
                            'p1': op['analysis'].get('punto_1', {}).get('price', 0),
                            'p0': op['analysis'].get('punto_0', {}).get('price', 0),
                            'p1_time': op['analysis'].get('punto_1', {}).get('time'),
                            'p0_time': op['analysis'].get('punto_0', {}).get('time'),
                            'entrada': op['analysis'].get('precio_entrada', 0),
                            'tp': op['analysis'].get('precio_tp', 0),
                            'sl_trigger': op['analysis'].get('precio_sl_trigger', 0),
                            'sl_definitivo': op['analysis'].get('precio_sl_definitivo', 0),
                            'beneficio_pct': op['analysis'].get('beneficio_esperado_pct', 0),
                            'patron': op['analysis'].get('patron_recuperacion', ''),
                            'score': op['score'],
                            'entry_fib': op['analysis'].get('entry_level_usado', config.get('entry_fib_level', 0.618)),
                            'tp_fib': op['analysis'].get('tp_level_usado', config.get('tp_fib_level', 0.382)),
                            'sl_trigger_fib': config.get('sl_trigger_fib', 0.886),
                            'sl_rebote_fib': config.get('sl_rebote_fib', 0.786),
                            'sl_definitivo_fib': config.get('sl_definitivo_fib', 0.95),
                        }
                    }
                    total_activas += 1
                    
                    # MODO REAL: Colocar LIMIT BUY en Binance
                    if not config.get('modo_demo', True) and self.orders._is_configured():
                        self._colocar_limit_buy_binance(symbol, self.ordenes_pendientes[symbol], config)
                    
                    # Log compacto en 1 línea con patrón
                    patron_tag = f" | 🔍{patron}" if patron and patron != 'DESCONOCIDO' else ""
                    niveles_tag = f" | Fib:{entry_lvl:.3f}/{tp_lvl:.3f}" if patron and patron != 'DESCONOCIDO' else ""
                    mag_info_log = analysis.get('p0p1_magnetico', {})
                    mag_tag = ""
                    if mag_info_log.get('p1_movido') or mag_info_log.get('p0_movido'):
                        mag_tag = f" | 🧲MAG(rango-{mag_info_log.get('rango_reducido_pct', 0):.0f}% P1f:{mag_info_log.get('p1_fuerza', 0):.0f} P0f:{mag_info_log.get('p0_fuerza', 0):.0f})"
                    self.log(f"📋 ORDEN: {symbol} | {op['timeframe']} | Score:{op['score']:.0f} | P1:{fmt_precio(p1)} → P0:{fmt_precio(p0)} | Entr:{fmt_precio(precio_entrada)} | TP:{fmt_precio(precio_tp)} | +{beneficio_esp:.1f}%{patron_tag}{niveles_tag}{mag_tag}", "INFO")
    
    def _sincronizar_con_binance(self, config):
        """SINCRONIZACIÓN COMPLETA con Binance.
        Detecta y reconcilia:
        A) Tokens comprados que el bot no conoce → adoptar + OCO
        B) Órdenes abiertas que el bot no conoce → cancelar
        C) Órdenes del bot que ya no existen en Binance → limpiar
        D) Posiciones del bot cuyos tokens desaparecieron → limpiar
        """
        if not self.orders._is_configured():
            return
        
        self.log("🔄 Sincronizando con Binance...", "INFO")
        
        hold_coins = [c.upper().strip() for c in config.get('hold_coins', [])]
        quote = config.get('pares_trading', ['USDC'])[0]
        
        # === CONSULTAR BINANCE ===
        balances = self.orders.get_all_balances(min_value_usdc=0)
        open_orders = self.orders.get_open_orders()
        
        if balances is None or open_orders is None:
            self.log("⚠️ No se pudo conectar con Binance para sincronizar", "WARNING")
            return
        
        # Mapear order IDs de Binance para búsqueda rápida
        binance_order_ids = set()
        binance_orders_by_symbol = {}
        for order in open_orders:
            binance_order_ids.add(order['orderId'])
            sym = order['symbol']
            if sym not in binance_orders_by_symbol:
                binance_orders_by_symbol[sym] = []
            binance_orders_by_symbol[sym].append(order)
        
        # Mapear lo que el bot conoce
        bot_order_ids = set()
        for sym, ord_data in self.ordenes_pendientes.items():
            oid = ord_data.get('binance_order_id')
            if oid:
                bot_order_ids.add(oid)
        # También incluir los order IDs de las OCO de posiciones activas
        for sym, pos_data in self.open_positions.items():
            oco_orders = pos_data.get('binance_oco_orders', [])
            for oco_ord in oco_orders:
                oid = oco_ord.get('orderId')
                if oid:
                    bot_order_ids.add(oid)
        
        cambios = 0
        
        # === A) TOKENS EN BINANCE QUE EL BOT NO CONOCE ===
        for asset, bal in balances.items():
            if asset in hold_coins:
                continue
            
            symbol = asset + quote
            free_qty = bal['free']
            
            # Verificar valor en USDC
            try:
                precio = self.market.get_current_price(symbol)
            except:
                continue
            if precio <= 0:
                continue
            
            valor = free_qty * precio
            if valor < 3.0:  # Dust
                continue
            
            # ¿Ya la conocemos?
            if symbol in self.open_positions:
                continue
            if symbol in self.ordenes_pendientes:
                continue
            
            # === TOKEN HUÉRFANO: Adoptar ===
            self.log(f"🔍 SYNC: {symbol} encontrado en Binance ({free_qty:.6f} = {valor:.1f} USDC) - No está en el bot", "WARNING")
            
            # Obtener precio REAL de compra de Binance
            real_buy_price, real_buy_qty, buy_time_ms = self.orders.get_last_buy_price(symbol)
            if real_buy_price:
                from datetime import timezone
                buy_date = datetime.fromtimestamp(buy_time_ms / 1000, tz=timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
                self.log(f"   📊 Precio compra real: {fmt_precio(real_buy_price)} | Qty: {real_buy_qty} | Fecha: {buy_date}", "INFO")
                precio_entrada_real = real_buy_price
            else:
                self.log(f"   ⚠️ No se encontró trade de compra, usando precio actual como referencia", "WARNING")
                precio_entrada_real = precio
            
            # Intentar analizar para encontrar P1/P0
            adopted = False
            for tf in ['1h', '4h', '1d']:
                try:
                    analysis = self.analyzer.analizar_par(symbol, tf, config, modo_monitoreo=True)
                    if analysis.get('status') == 'OK':
                        p1 = analysis['punto_1']
                        p0 = analysis['punto_0']
                        tp = analysis['precio_tp']
                        sl_def = analysis['precio_sl_definitivo']
                        sl_trigger = analysis['precio_sl_trigger']
                        
                        # Crear posición
                        with self._lock:
                            self.open_positions[symbol] = {
                                'symbol': symbol,
                                'timeframe': tf,
                                'cantidad': free_qty,
                                'precio_entrada_real': precio_entrada_real,
                                'fecha_entrada': datetime.utcfromtimestamp(buy_time_ms / 1000).isoformat() if buy_time_ms else datetime.utcnow().isoformat(),
                                'p1_suelo': p1,
                                'p1_fecha': None,
                                'p0_maximo': p0,
                                'p0_fecha': None,
                                'analysis': analysis,
                                'valores_originales': {
                                    'precio_entrada': analysis['precio_entrada'],
                                    'precio_tp': tp,
                                    'precio_sl_trigger': sl_trigger,
                                    'precio_sl_definitivo': sl_def,
                                    'punto_1': p1,
                                    'punto_0': p0,
                                },
                                'score': 0,
                                'modo': 'REAL',  # CRÍTICO: REAL para que ventas funcionen
                            }
                        
                        # Colocar OCO de protección
                        result = self.orders.place_oco_sell(symbol, free_qty, tp, sl_trigger, sl_def)
                        if result.get('success'):
                            self.open_positions[symbol]['binance_oco_id'] = result['orderListId']
                            self.open_positions[symbol]['binance_oco_orders'] = result['orders']
                            self.open_positions[symbol]['oco_tp_vigente'] = result['tp_price']
                            self.open_positions[symbol]['oco_sl_vigente'] = result['sl_limit']
                            self.log(f"✅ SYNC: {symbol} adoptada | TP:{fmt_precio(result['tp_price'])} | SL:{fmt_precio(result['sl_limit'])} | TF:{tf}", "SUCCESS")
                        else:
                            self.log(f"⚠️ SYNC: {symbol} adoptada pero OCO falló: {result.get('error', '?')}", "WARNING")
                        
                        # Notificar Telegram
                        if config.get('telegram_bot_token') and config.get('telegram_chat_id'):
                            enviar_telegram(config['telegram_bot_token'], config['telegram_chat_id'],
                                f"🔍 SYNC: Token huérfano adoptado\n{symbol} ({valor:.1f} USDC)\n🛡️ OCO colocada",
                                config, 'proteccion')
                        
                        adopted = True
                        cambios += 1
                        break
                except Exception as e:
                    continue
            
            if not adopted:
                # ANÁLISIS FALLÓ → Proteger igualmente con OCO básica basada en precio de compra
                self.log(f"⚠️ SYNC: {symbol} análisis Fibonacci falló en todas las temporalidades", "WARNING")
                self.log(f"   🛡️ Adoptando con protección básica (TP/SL por defecto desde precio compra)", "INFO")
                
                # Obtener precio actual para calcular TP/SL correctos
                try:
                    precio_actual = self.market.get_current_price(symbol)
                except:
                    precio_actual = 0
                
                # TP y SL por defecto basados en el precio de compra
                tp_pct_default = config.get('min_beneficio_pct', 3.0) / 100
                sl_pct_default = 0.05  # 5% SL de emergencia
                
                tp_basico = precio_entrada_real * (1 + tp_pct_default)
                sl_trigger_basico = precio_entrada_real * (1 - sl_pct_default * 0.8)
                sl_def_basico = precio_entrada_real * (1 - sl_pct_default)
                
                # CRÍTICO: Si el precio actual YA está por encima del TP básico,
                # ajustar TP por encima del precio actual (Binance exige TP > precio actual para SELL)
                if precio_actual > 0 and precio_actual >= tp_basico:
                    ganancia_actual = ((precio_actual - precio_entrada_real) / precio_entrada_real) * 100
                    
                    if ganancia_actual > 15:
                        # Ganancia grande → vender directamente a mercado
                        self.log(f"💰 SYNC: {symbol} ya en +{ganancia_actual:.1f}% → vendiendo a mercado", "SUCCESS")
                        asset_name_sell = symbol.replace(quote, '')
                        sell_qty = free_qty
                        try:
                            bal = self.orders.get_all_balances(min_value_usdc=0)
                            if bal and asset_name_sell in bal:
                                rf = bal[asset_name_sell].get('free', 0)
                                if 0 < rf < free_qty:
                                    sell_qty = rf
                        except:
                            pass
                        result_sell = self.orders.place_market_sell(symbol, sell_qty)
                        if result_sell.get('success'):
                            precio_venta = result_sell.get('avg_price', 0)
                            ben_pct = ((precio_venta - precio_entrada_real) / precio_entrada_real * 100) if precio_entrada_real > 0 else 0
                            ben_usd = (precio_venta - precio_entrada_real) * sell_qty
                            self.log(f"🟢 VENTA SYNC: {symbol} [REAL] | +{ben_pct:.2f}% | @ {fmt_precio(precio_venta)} | ${ben_usd:.2f}", "SUCCESS")
                            try:
                                self.stats.registrar_operacion(
                                    symbol=symbol, fecha_entrada=datetime.utcfromtimestamp(buy_time_ms / 1000).isoformat() if buy_time_ms else '',
                                    fecha_salida=datetime.utcnow().isoformat(),
                                    precio_entrada=precio_entrada_real, precio_salida=precio_venta,
                                    beneficio_pct=ben_pct, beneficio_usd=ben_usd,
                                    tipo='REAL', temporalidad='sync'
                                )
                            except:
                                pass
                            cambios += 1
                            continue  # No adoptar, ya vendida
                        else:
                            self.log(f"❌ SYNC: {symbol} MARKET SELL falló: {result_sell.get('error', '?')}", "ERROR")
                    
                    # Poner TP un % por encima del precio actual
                    tp_basico = precio_actual * (1 + tp_pct_default)
                    # SL en breakeven+ (proteger ganancia)
                    sl_trigger_basico = precio_entrada_real * 1.005  # +0.5% sobre entrada
                    sl_def_basico = precio_entrada_real * 0.998  # -0.2% (casi breakeven)
                    self.log(f"   📊 Precio actual {fmt_precio(precio_actual)} > TP básico → TP ajustado a {fmt_precio(tp_basico)}, SL en breakeven", "INFO")
                
                with self._lock:
                    self.open_positions[symbol] = {
                        'symbol': symbol,
                        'timeframe': 'sync',
                        'cantidad': free_qty,
                        'precio_entrada_real': precio_entrada_real,
                        'fecha_entrada': datetime.utcfromtimestamp(buy_time_ms / 1000).isoformat() if buy_time_ms else datetime.utcnow().isoformat(),
                        'p1_suelo': 0,
                        'p0_maximo': 0,
                        'analysis': {},
                        'valores_originales': {
                            'precio_entrada': precio_entrada_real,
                            'tp': tp_basico,
                            'sl_trigger': sl_trigger_basico,
                            'sl_definitivo': sl_def_basico,
                            'precio_tp': tp_basico,
                            'precio_sl_trigger': sl_trigger_basico,
                            'precio_sl_definitivo': sl_def_basico,
                            'p1': 0,
                            'p0': 0,
                        },
                        'score': 0,
                        'modo': 'REAL',
                    }
                
                # Colocar OCO de protección básica
                # Usar balance real (fees)
                asset_name = symbol.replace(quote, '')
                oco_qty = free_qty
                try:
                    bal_check = self.orders.get_all_balances(min_value_usdc=0)
                    if bal_check and asset_name in bal_check:
                        real_free = bal_check[asset_name].get('free', 0)
                        if 0 < real_free < free_qty:
                            oco_qty = real_free
                            self.open_positions[symbol]['cantidad'] = real_free
                except:
                    pass
                
                result = self.orders.place_oco_sell(symbol, oco_qty, tp_basico, sl_trigger_basico, sl_def_basico)
                if result.get('success'):
                    self.open_positions[symbol]['binance_oco_id'] = result['orderListId']
                    self.open_positions[symbol]['binance_oco_orders'] = result['orders']
                    self.open_positions[symbol]['oco_tp_vigente'] = result['tp_price']
                    self.open_positions[symbol]['oco_sl_vigente'] = result['sl_limit']
                    self.log(f"✅ SYNC: {symbol} protegida | Compra:{fmt_precio(precio_entrada_real)} | TP:{fmt_precio(result['tp_price'])} | SL:{fmt_precio(result['sl_limit'])}", "SUCCESS")
                else:
                    self.log(f"❌ SYNC: {symbol} OCO falló: {result.get('error', '?')} → Bot monitoreará internamente", "ERROR")
                
                self._save_state()
                
                if config.get('telegram_bot_token') and config.get('telegram_chat_id'):
                    enviar_telegram(config['telegram_bot_token'], config['telegram_chat_id'],
                        f"🔍 SYNC: Token huérfano adoptado\n{symbol} ({valor:.1f} USDC)\n💰 Compra: {fmt_precio(precio_entrada_real)}\n🛡️ TP:{fmt_precio(tp_basico)} / SL:{fmt_precio(sl_def_basico)}",
                        config, 'proteccion')
                
                cambios += 1
        
        # === B) ÓRDENES EN BINANCE QUE EL BOT NO CONOCE ===
        for order in open_orders:
            oid = order['orderId']
            sym = order['symbol']
            side = order.get('side', '')
            
            if oid in bot_order_ids:
                continue  # El bot la conoce
            
            # ¿Es una orden OCO de una posición conocida?
            if sym in self.open_positions:
                continue  # Probablemente es la OCO SELL
            
            # BUY orders huérfanas → analizar y decidir
            if side == 'BUY':
                price = float(order.get('price', 0))
                qty = float(order.get('origQty', 0))
                self.log(f"🔍 SYNC: Orden huérfana {sym} BUY @ {fmt_precio(price)} qty:{qty} (OrderId:{oid})", "WARNING")
                
                # Analizar si la moneda sigue siendo buena
                adopted_order = False
                for tf in ['1h', '4h', '1d']:
                    try:
                        analysis = self.analyzer.analizar_par(sym, tf, config, modo_monitoreo=False)
                        if analysis.get('status') == 'OK':
                            score_data = self.analyzer.calcular_score(sym, None, analysis, config.get('estrategia_scoring', 'C'), config)
                            score = score_data[0] if isinstance(score_data, tuple) else 0
                            min_score = config.get('min_score_compra', 60)
                            
                            if score >= min_score * 0.7:  # 70% del mínimo para dar margen
                                # Adoptar la orden
                                with self._lock:
                                    self.ordenes_pendientes[sym] = {
                                        'symbol': sym,
                                        'timeframe': tf,
                                        'precio_entrada': price,
                                        'analysis': analysis,
                                        'score': score,
                                        'binance_order_id': oid,
                                        'fecha_creacion': datetime.utcnow().isoformat(),
                                        'valores_originales': {
                                            'precio_entrada': analysis.get('precio_entrada', price),
                                            'precio_tp': analysis.get('precio_tp', 0),
                                            'precio_sl_trigger': analysis.get('precio_sl_trigger', 0),
                                            'precio_sl_definitivo': analysis.get('precio_sl_definitivo', 0),
                                            'punto_1': analysis.get('punto_1', 0),
                                            'punto_0': analysis.get('punto_0', 0),
                                        },
                                        'modo': 'REAL',  # CRÍTICO: debe ser REAL para que ventas se ejecuten en Binance
                                    }
                                self.log(f"✅ SYNC: Orden {sym} adoptada | Score:{score:.0f} | Entry:{fmt_precio(price)} | TF:{tf}", "SUCCESS")
                                adopted_order = True
                                cambios += 1
                                break
                            else:
                                self.log(f"   📊 {sym} score {score:.0f} < {min_score * 0.7:.0f} en {tf}, probando otro TF...", "INFO")
                    except:
                        continue
                
                if not adopted_order:
                    # Score malo en todas las temporalidades → cancelar
                    self.log(f"🗑️ SYNC: {sym} BUY @ {fmt_precio(price)} score insuficiente → Cancelando", "WARNING")
                    self.orders.cancel_order(sym, oid)
                    cambios += 1
            
            # SELL orders huérfanas → verificar si tenemos tokens, si no cancelar
            elif side == 'SELL':
                price = float(order.get('price', 0))
                qty = float(order.get('origQty', 0))
                order_type = order.get('type', '')
                self.log(f"🔍 SYNC: Orden huérfana {sym} SELL ({order_type}) @ {fmt_precio(price)} qty:{qty} (OrderId:{oid})", "WARNING")
                
                # ¿Tenemos los tokens para esta venta?
                asset = sym.replace(quote, '')
                asset_bal = balances.get(asset, {}).get('free', 0) + balances.get(asset, {}).get('locked', 0)
                
                if asset_bal >= qty * 0.9:  # Tenemos tokens (con margen por fees)
                    # Hay tokens → buscar precio de compra y adoptar como posición
                    real_buy_price, real_buy_qty, buy_time_ms = self.orders.get_last_buy_price(sym)
                    precio_compra = real_buy_price if real_buy_price else price * 0.95  # Estimar si no hay datos
                    
                    if sym not in self.open_positions:
                        # Buscar las dos patas de la OCO (LIMIT_MAKER = TP, STOP_LOSS_LIMIT = SL)
                        oco_list_id = order.get('orderListId')
                        oco_list_id = oco_list_id if oco_list_id and oco_list_id != -1 else None
                        precio_tp_oco = 0.0
                        precio_sl_trigger = precio_compra * 0.96
                        precio_sl_oco = precio_compra * 0.95
                        hermanas = binance_orders_by_symbol.get(sym, [])
                        for h in hermanas:
                            if oco_list_id and h.get('orderListId') != oco_list_id:
                                continue
                            h_type = h.get('type', '')
                            h_price = float(h.get('price', 0))
                            h_stop = float(h.get('stopPrice', 0))
                            if h_type == 'LIMIT_MAKER' and h_price > 0:
                                precio_tp_oco = h_price
                            elif h_type in ('STOP_LOSS_LIMIT', 'STOP_LOSS') and h_stop > 0:
                                precio_sl_trigger = h_stop
                                precio_sl_oco = h_price if h_price > 0 else h_stop * 0.999
                        if precio_tp_oco <= 0:
                            precio_tp_oco = price if order_type == 'LIMIT_MAKER' else precio_compra * 1.05

                        # Ingeniería inversa Fibonacci: estimar P0 y P1
                        p1_est = precio_compra * 0.97
                        rango_est = (precio_tp_oco - precio_compra) / 0.236 if precio_tp_oco > precio_compra else precio_compra * 0.1
                        p0_est = precio_compra + rango_est * 0.618
                        benef_pct = ((precio_tp_oco - precio_compra) / precio_compra * 100) if precio_compra > 0 else 0

                        self.log(f"   📊 Adoptando {sym} | Compra:{fmt_precio(precio_compra)} TP:{fmt_precio(precio_tp_oco)} (+{benef_pct:.1f}%) SL:{fmt_precio(precio_sl_oco)} | OCO:{oco_list_id}", "INFO")
                        with self._lock:
                            self.open_positions[sym] = {
                                'symbol': sym,
                                'timeframe': 'sync',
                                'cantidad': qty,
                                'cantidad_comprada': qty,
                                'precio_entrada_real': precio_compra,
                                'fecha_entrada': datetime.utcfromtimestamp(buy_time_ms / 1000).isoformat() if buy_time_ms else datetime.utcnow().isoformat(),
                                'p1_suelo': p1_est,
                                'p0_maximo': p0_est,
                                'score': 0,
                                'modo': 'REAL',
                                'binance_oco_id': oco_list_id,
                                '_oco_externa': True,
                                'analysis': {
                                    'precio_actual': precio_compra,
                                    'precio_tp': precio_tp_oco,
                                    'precio_sl_trigger': precio_sl_trigger,
                                    'precio_sl_definitivo': precio_sl_oco,
                                    'beneficio_esperado_pct': benef_pct,
                                    'punto_1': {'price': p1_est},
                                    'punto_0': {'price': p0_est},
                                },
                                'valores_originales': {
                                    'entrada': precio_compra,
                                    'precio_entrada': precio_compra,
                                    'tp': precio_tp_oco,
                                    'precio_tp': precio_tp_oco,
                                    'sl_trigger': precio_sl_trigger,
                                    'sl_definitivo': precio_sl_oco,
                                    'precio_sl_trigger': precio_sl_trigger,
                                    'precio_sl_definitivo': precio_sl_oco,
                                    'p1': p1_est,
                                    'p0': p0_est,
                                    'beneficio_pct': benef_pct,
                                },
                            }
                        oco_tag = f" | OCO:{oco_list_id}" if oco_list_id else ""
                        self.log(f"✅ SYNC: {sym} adoptada con OCO | TP:{fmt_precio(precio_tp_oco)} SL:{fmt_precio(precio_sl_oco)}{oco_tag}", "SUCCESS")
                        cambios += 1
                else:
                    # No tenemos tokens → orden SELL sin sentido, cancelar
                    self.log(f"🗑️ SYNC: {sym} SELL @ {fmt_precio(price)} sin tokens ({asset_bal:.2f}) → Cancelando", "WARNING")
                    try:
                        self.orders.cancel_order(sym, oid)
                    except Exception as e:
                        self.log(f"⚠️ SYNC: No se pudo cancelar {sym} SELL: {str(e)[:60]}", "WARNING")
                    cambios += 1
        
        # === C) ÓRDENES DEL BOT QUE YA NO ESTÁN EN BINANCE ===
        with self._lock:
            for sym in list(self.ordenes_pendientes.keys()):
                ord_data = self.ordenes_pendientes[sym]
                oid = ord_data.get('binance_order_id')
                if not oid:
                    continue
                
                if oid not in binance_order_ids:
                    # La orden desapareció de Binance → fue ejecutada o cancelada externamente
                    asset = sym.replace(quote, '')
                    bal_asset = balances.get(asset, {}).get('free', 0)
                    
                    if bal_asset > 0:
                        try:
                            precio_actual = self.market.get_current_price(sym)
                        except:
                            precio_actual = 0
                        valor_asset = bal_asset * precio_actual if precio_actual > 0 else 0
                        
                        if valor_asset > 3.0:
                            # La orden se ejecutó → será adoptada en paso A del siguiente sync
                            self.log(f"⚡ SYNC: {sym} orden {oid} ejecutada externamente ({bal_asset:.6f} tokens)", "SUCCESS")
                        else:
                            self.log(f"🗑️ SYNC: {sym} orden {oid} desapareció y no hay tokens. Limpiando.", "WARNING")
                    else:
                        self.log(f"🗑️ SYNC: {sym} orden {oid} cancelada externamente. Limpiando.", "WARNING")
                    
                    # Limpiar del bot
                    del self.ordenes_pendientes[sym]
                    cambios += 1
        
        # === D) POSICIONES DEL BOT SIN TOKENS EN BINANCE ===
        with self._lock:
            for sym in list(self.open_positions.keys()):
                pos = self.open_positions[sym]
                if pos.get('modo') == 'DEMO':
                    continue  # No verificar posiciones demo
                
                asset = sym.replace(quote, '')
                bal_asset = balances.get(asset, {}).get('free', 0)
                locked_asset = balances.get(asset, {}).get('locked', 0)
                total_asset = bal_asset + locked_asset
                
                try:
                    precio_actual = self.market.get_current_price(sym)
                except:
                    precio_actual = 0
                
                valor_total = total_asset * precio_actual if precio_actual > 0 else 0
                
                if valor_total < 1.0:  # Tokens desaparecieron (vendidos por OCO o manualmente)
                    precio_entrada = pos.get('precio_entrada_real', 0)
                    beneficio_pct = ((precio_actual - precio_entrada) / precio_entrada * 100) if precio_entrada > 0 and precio_actual > 0 else 0
                    
                    self.log(f"🔍 SYNC: {sym} posición sin tokens en Binance. OCO/venta externa detectada. P&L ≈ {beneficio_pct:+.1f}%", "WARNING")
                    
                    # Registrar en estadísticas
                    try:
                        self.stats.registrar_operacion(
                            symbol=sym,
                            fecha_entrada=pos.get('fecha_entrada', ''),
                            fecha_salida=datetime.utcnow().isoformat(),
                            precio_entrada=precio_entrada,
                            precio_salida=precio_actual,
                            beneficio_pct=beneficio_pct,
                            beneficio_usd=(precio_actual - precio_entrada) * pos.get('cantidad', 0),
                            tipo=pos.get('modo', 'REAL'),
                            temporalidad=pos.get('timeframe', 'sync')
                        )
                    except Exception as e:
                        self.log(f"⚠️ {sym} - Error registrando stats sync: {str(e)[:60]}", "WARNING")
                    
                    del self.open_positions[sym]
                    
                    if config.get('telegram_bot_token') and config.get('telegram_chat_id'):
                        enviar_telegram(config['telegram_bot_token'], config['telegram_chat_id'],
                            f"🔍 SYNC: {sym} vendida externamente\n💰 P&L: ≈{beneficio_pct:+.1f}%",
                            config, 'venta')
                    cambios += 1
        
        if cambios > 0:
            self.log(f"🔄 SYNC completada: {cambios} cambio(s) detectados", "SUCCESS")
            self._save_state()
        else:
            self.log("✅ SYNC: Binance y bot sincronizados", "INFO")

    def _colocar_limit_buy_binance(self, symbol, orden, config):
        """Coloca LIMIT BUY en Binance usando el saldo REAL disponible.
        Si el saldo es menor que el capital configurado, usa lo que hay.
        Si no hay saldo suficiente para el mínimo, espera al próximo ciclo.
        SEGURIDAD: Verifica que no tengamos ya tokens de esta moneda."""
        precio_entrada = orden.get('precio_entrada', 0)
        tamano_config = calcular_tamano_posicion(config)
        if precio_entrada <= 0 or tamano_config <= 0:
            return
        
        # SEGURIDAD: Verificar que no tengamos ya tokens (orden huérfana ejecutada)
        asset = symbol.replace('USDC', '')
        try:
            holding = get_binance_balance(
                config.get('binance_api_key', ''),
                config.get('binance_api_secret', ''),
                asset=asset
            )
            if holding is not None and holding > 0:
                valor_holding = holding * precio_entrada
                if valor_holding > 3.0:  # Más de 3 USDC en tokens
                    self.log(f"⚠️ {symbol} - Ya tienes {holding:.4f} {asset} en Binance (≈{valor_holding:.1f} USDC). Orden cancelada para evitar duplicados.", "WARNING")
                    self._eliminar_orden_pendiente(symbol)
                    return
        except:
            pass  # Si falla el check, continuar normalmente
        
        # Cooldown: no reintentar saldo insuficiente más de 1 vez cada 5 minutos
        cooldown_key = f"balance_{symbol}"
        ahora = datetime.utcnow()
        ultimo_intento = self._agotada_cooldown.get(cooldown_key)
        if ultimo_intento and (ahora - ultimo_intento).total_seconds() < 300:
            return  # Esperar sin logear
        
        # Consultar saldo REAL disponible en Binance
        try:
            saldo_disponible = get_binance_balance(
                config.get('binance_api_key', ''), 
                config.get('binance_api_secret', '')
            )
        except:
            saldo_disponible = None
        
        if saldo_disponible is None or saldo_disponible <= 0:
            self._agotada_cooldown[cooldown_key] = ahora
            self.log(f"⏳ {symbol} - Sin saldo USDC disponible, reintentando en 5 min", "WARNING")
            return
        
        # Usar el MÍNIMO entre capital configurado y saldo disponible
        # Dejar 1 USDC de margen para comisiones
        tamano_real = min(tamano_config, saldo_disponible - 1.0)
        
        # Verificar mínimo (Binance requiere ~5-10 USDC por orden)
        min_notional = 5.0
        if tamano_real < min_notional:
            self._agotada_cooldown[cooldown_key] = ahora
            self.log(f"⏳ {symbol} - Saldo disponible {saldo_disponible:.2f} USDC insuficiente (min: {min_notional}), esperando", "WARNING")
            return
        
        if tamano_real < tamano_config:
            self.log(f"💰 {symbol} - Usando saldo disponible: {tamano_real:.2f} USDC (de {tamano_config:.2f} configurados)", "INFO")
        
        result = self.orders.place_limit_buy(symbol, precio_entrada, tamano_real)
        if result.get('success'):
            orden['binance_order_id'] = result['orderId']
            orden['binance_price'] = result['price']
            orden['binance_qty'] = result['quantity']
            orden['binance_placement_failed'] = False
            # Limpiar cooldown
            self._agotada_cooldown.pop(cooldown_key, None)
            self.log(f"📤 {symbol} - LIMIT BUY colocada en Binance @ {fmt_precio(result['price'])} | Qty:{result['quantity']:.6f} | {tamano_real:.2f} USDC | OrderId:{result['orderId']}", "SUCCESS")
            # Notificar orden colocada
            if config.get('telegram_bot_token') and config.get('telegram_chat_id'):
                enviar_telegram(config['telegram_bot_token'], config['telegram_chat_id'],
                    f"📤 ORDEN COLOCADA {symbol}\n💰 Precio: {fmt_precio(result['price'])}\n📊 {tamano_real:.2f} USDC",
                    config, 'orden')
        else:
            error_msg = result.get('error', '?')
            if 'insufficient' in error_msg.lower():
                self._agotada_cooldown[cooldown_key] = ahora
                self.log(f"⏳ {symbol} - Saldo insuficiente en Binance, reintentando en 5 min", "WARNING")
            else:
                orden['binance_placement_failed'] = True
                self.log(f"❌ {symbol} - Error colocando LIMIT BUY: {error_msg}", "ERROR")
    
    def _rebalancear_ordenes_binance(self, config):
        """Rebalancea órdenes LIMIT BUY en Binance para que todas tengan el mismo capital.
        SEGURO: Verifica que cada cancelación funcione antes de continuar.
        Si hay error de red, aborta sin dejar órdenes huérfanas."""
        
        # 1. Identificar órdenes activas en Binance
        ordenes_binance = []
        for symbol, orden in self.ordenes_pendientes.items():
            if orden.get('binance_order_id'):
                qty = orden.get('binance_qty', 0)
                price = orden.get('binance_price', orden.get('precio_entrada', 0))
                usdc_actual = qty * price if qty > 0 and price > 0 else 0
                ordenes_binance.append({
                    'symbol': symbol,
                    'usdc': usdc_actual,
                    'order_id': orden['binance_order_id']
                })
        
        # Órdenes pendientes sin colocar en Binance
        ordenes_sin_binance = [s for s, o in self.ordenes_pendientes.items() 
                               if not o.get('binance_order_id')]
        
        total_ordenes = len(ordenes_binance) + len(ordenes_sin_binance)
        if total_ordenes < 2:
            return  # Nada que rebalancear
        
        # 2. Obtener saldo libre actual
        try:
            saldo_libre = get_binance_balance(
                config.get('binance_api_key', ''),
                config.get('binance_api_secret', '')
            )
            if saldo_libre is None:
                return  # Error de red
        except:
            return
        
        # 3. Calcular capital total y por orden
        usdc_en_ordenes = sum(o['usdc'] for o in ordenes_binance)
        capital_total = usdc_en_ordenes + saldo_libre
        
        if capital_total < 10:
            return
        
        capital_por_orden = capital_total / total_ordenes
        
        if capital_por_orden < 5:
            return  # No vale la pena
        
        # 4. Verificar si hay desbalance (>15% de diferencia o hay órdenes sin colocar)
        necesita_rebalanceo = len(ordenes_sin_binance) > 0
        
        if not necesita_rebalanceo:
            for o in ordenes_binance:
                diff_pct = abs(o['usdc'] - capital_por_orden) / capital_por_orden * 100
                if diff_pct > 15:
                    necesita_rebalanceo = True
                    break
        
        if not necesita_rebalanceo:
            return
        
        # 5. VERIFICAR CONEXIÓN antes de hacer nada
        try:
            test_balance = get_binance_balance(
                config.get('binance_api_key', ''),
                config.get('binance_api_secret', '')
            )
            if test_balance is None:
                self.log("⚠️ Rebalance abortado: no se puede conectar a Binance", "WARNING")
                return
        except:
            self.log("⚠️ Rebalance abortado: error de red", "WARNING")
            return
        
        # 6. Cancelar órdenes verificando cada una
        self.log(f"⚖️ Rebalanceando {total_ordenes} órdenes: {capital_por_orden:.2f} USDC cada una (total: {capital_total:.2f})", "INFO")
        
        canceladas_ok = []
        for o in ordenes_binance:
            orden = self.ordenes_pendientes.get(o['symbol'])
            if not orden:
                continue
            
            cancelada = self._cancelar_orden_binance_pendiente(o['symbol'], orden)
            if cancelada:
                orden.pop('binance_order_id', None)
                orden.pop('binance_price', None)
                orden.pop('binance_qty', None)
                canceladas_ok.append(o['symbol'])
            else:
                # ABORTAR: no pudimos cancelar → no seguir
                self.log(f"⚠️ Rebalance ABORTADO: no se pudo cancelar {o['symbol']}", "WARNING")
                return
        
        # 7. Limpiar flags de TODAS las órdenes pendientes
        for symbol, orden in self.ordenes_pendientes.items():
            orden.pop('binance_placement_failed', None)
        
        # 8. Esperar para que Binance libere los fondos
        time.sleep(1)
        
        # 9. Recolocar TODAS equitativamente
        for symbol, orden in self.ordenes_pendientes.items():
            if orden.get('binance_order_id'):
                continue
            
            precio_entrada = orden.get('precio_entrada', 0)
            if precio_entrada <= 0:
                continue
            
            result = self.orders.place_limit_buy(symbol, precio_entrada, capital_por_orden)
            if result.get('success'):
                orden['binance_order_id'] = result['orderId']
                orden['binance_price'] = result['price']
                orden['binance_qty'] = result['quantity']
                self.log(f"  ⚖️ {symbol} - LIMIT BUY @ {fmt_precio(result['price'])} | {capital_por_orden:.2f} USDC", "SUCCESS")
            else:
                self.log(f"  ⚠️ {symbol} - Error rebalanceando: {result.get('error', '?')}", "WARNING")

    def _cancelar_orden_binance_pendiente(self, symbol, orden):
        """Cancela LIMIT BUY en Binance. Retorna True si se canceló, False si falló."""
        order_id = orden.get('binance_order_id')
        if not order_id:
            return True  # No hay nada que cancelar
        try:
            result = self.orders.cancel_order(symbol, order_id)
            if result.get('status') == 'CANCELED':
                self.log(f"🗑️ {symbol} - LIMIT BUY cancelada en Binance (OrderId:{order_id})", "INFO")
                return True
            elif result.get('code') == -2011:
                # Order not found (ya fue cancelada o ejecutada)
                self.log(f"⚠️ {symbol} - Orden {order_id} ya no existe en Binance (ejecutada o cancelada)", "WARNING")
                return True
            else:
                self.log(f"❌ {symbol} - Error cancelando orden {order_id}: {result.get('msg', result.get('error', '?'))}", "ERROR")
                return False
        except Exception as e:
            self.log(f"❌ {symbol} - Error de red cancelando orden {order_id}: {str(e)[:60]}", "ERROR")
            return False
    
    def _eliminar_orden_pendiente(self, symbol):
        """Elimina una orden pendiente cancelando LIMIT BUY de Binance si existe.
        SOLO elimina si la cancelación en Binance fue exitosa."""
        if symbol not in self.ordenes_pendientes:
            return True
        orden = self.ordenes_pendientes[symbol]
        # Cancelar en Binance si tiene order_id
        if orden.get('binance_order_id') and self.orders._is_configured():
            if not self._cancelar_orden_binance_pendiente(symbol, orden):
                self.log(f"⚠️ {symbol} - No se pudo cancelar en Binance, orden pendiente conservada", "WARNING")
                return False
        del self.ordenes_pendientes[symbol]
        return True
    
    def _cancelar_orden_binance_si_existe(self, symbol, config):
        """Si ya hay una orden pendiente para este symbol con LIMIT BUY en Binance, cancelarla"""
        es_real = not config.get('modo_demo', True) and self.orders._is_configured()
        if es_real and symbol in self.ordenes_pendientes:
            orden_vieja = self.ordenes_pendientes[symbol]
            if orden_vieja.get('binance_order_id'):
                self.log(f"🔄 {symbol} - Cancelando LIMIT BUY vieja antes de reemplazar", "INFO")
                self._cancelar_orden_binance_pendiente(symbol, orden_vieja)
    
    def _registrar_compra_y_poner_oco(self, symbol, orden, config, fill_price, fill_qty):
        """Cuando Binance ejecuta LIMIT BUY: registra posición + coloca OCO SELL"""
        analysis = orden.get('analysis', {})
        valores_orig = orden.get('valores_originales', {})
        p1_orig = valores_orig.get('p1', analysis.get('punto_1', {}).get('price', 0))
        p0_orig = valores_orig.get('p0', analysis.get('punto_0', {}).get('price', 0))
        tp_orig = valores_orig.get('tp', analysis.get('precio_tp', 0))
        
        p1_fecha = analysis.get('punto_1', {}).get('time')
        p0_fecha = analysis.get('punto_0', {}).get('time')
        
        self.open_positions[symbol] = {
            'symbol': symbol,
            'timeframe': orden.get('timeframe', '1h'),
            'cantidad': fill_qty,
            'precio_entrada_real': fill_price,
            'fecha_entrada': datetime.utcnow().isoformat(),
            'p1_suelo': p1_orig,
            'p1_fecha': p1_fecha,
            'p0_maximo': p0_orig,
            'p0_fecha': p0_fecha,
            'analysis': analysis,
            'valores_originales': valores_orig,
            'score': orden.get('score', 0),
            'detalles_score': orden.get('detalles_score', {}),
            'modo': 'REAL'
        }
        
        if symbol in self.ordenes_pendientes:
            self._eliminar_orden_pendiente(symbol)
        
        beneficio_esp = ((tp_orig - fill_price) / fill_price) * 100 if fill_price > 0 else 0
        self.log(f"🟢 COMPRA: {symbol} @ {fmt_precio(fill_price)} | P1:{fmt_precio(p1_orig)} → P0:{fmt_precio(p0_orig)} | TP:{fmt_precio(tp_orig)} | +{beneficio_esp:.1f}%", "SUCCESS")
        
        # Colocar OCO SELL inmediatamente
        sl_definitivo = valores_orig.get('sl_definitivo', 0)
        if tp_orig > 0 and sl_definitivo > 0 and fill_qty > 0:
            # SL trigger un poco por encima del SL definitivo para dar margen
            sl_trigger = valores_orig.get('sl_trigger', sl_definitivo * 1.002)
            
            # CRÍTICO: Usar balance REAL (fees reducen qty recibida)
            quote = config.get('pares_trading', ['USDC'])[0]
            asset = symbol.replace(quote, '')
            oco_qty = fill_qty
            try:
                balances = self.orders.get_all_balances(min_value_usdc=0)
                if balances and asset in balances:
                    real_free = balances[asset].get('free', 0)
                    if 0 < real_free < fill_qty:
                        oco_qty = real_free
                        self.open_positions[symbol]['cantidad'] = real_free  # Actualizar
            except:
                pass
            
            result = self.orders.place_oco_sell(symbol, oco_qty, tp_orig, sl_trigger, sl_definitivo)
            if result.get('success'):
                self.open_positions[symbol]['binance_oco_id'] = result['orderListId']
                self.open_positions[symbol]['binance_oco_orders'] = result['orders']
                self.open_positions[symbol]['oco_tp_vigente'] = result['tp_price']
                self.open_positions[symbol]['oco_sl_vigente'] = result['sl_limit']
                self.log(f"🛡️ {symbol} - OCO SELL colocada | TP:{fmt_precio(result['tp_price'])} | SL:{fmt_precio(result['sl_trigger'])} → {fmt_precio(result['sl_limit'])}", "SUCCESS")
            else:
                self.log(f"⚠️ {symbol} - Error colocando OCO: {result.get('error', '?')} → Bot monitoreará SL internamente", "WARNING")
        
        # Notificar Telegram
        if config.get('telegram_bot_token') and config.get('telegram_chat_id'):
            msg = f"🟢 COMPRA REAL {symbol}\n💰 Precio: {fmt_precio(fill_price)}\n📊 Qty: {fill_qty:.6f}\n🛡️ OCO: TP {fmt_precio(tp_orig)} / SL {fmt_precio(sl_definitivo)}"
            enviar_telegram(config['telegram_bot_token'], config['telegram_chat_id'], msg, config, 'compra')
    
    def _actualizar_oco_binance(self, symbol, pos_data, config, nuevo_tp, nuevo_sl_trigger, nuevo_sl_definitivo):
        """Cancela OCO vieja y coloca nueva con niveles actualizados"""
        if not self.orders._is_configured():
            return
        
        oco_id = pos_data.get('binance_oco_id')
        if oco_id:
            # Verificar si OCO ya fue ejecutada antes de cancelar
            try:
                oco_status = self.orders.get_oco_status(symbol, oco_id)
                if oco_status:
                    list_status = oco_status.get('listOrderStatus') or oco_status.get('listStatusType', '')
                    if list_status == 'ALL_DONE':
                        # OCO ya ejecutada por Binance → cerrar posición
                        self.log(f"🏦 {symbol} - OCO ejecutada por Binance (detectada al actualizar)", "SUCCESS")
                        self._cerrar_posicion(symbol, 'TAKE_PROFIT', config)
                        return
            except:
                pass
            self.orders.cancel_oco(symbol, oco_id)
        
        cantidad = pos_data.get('cantidad', 0)
        if cantidad > 0 and nuevo_tp > 0 and nuevo_sl_definitivo > 0:
            result = self.orders.place_oco_sell(symbol, cantidad, nuevo_tp, nuevo_sl_trigger, nuevo_sl_definitivo)
            if result.get('success'):
                pos_data['binance_oco_id'] = result['orderListId']
                pos_data['binance_oco_orders'] = result['orders']
                pos_data['oco_tp_vigente'] = result['tp_price']
                pos_data['oco_sl_vigente'] = result['sl_limit']
                self.log(f"🔄 {symbol} - OCO actualizada | TP:{fmt_precio(result['tp_price'])} | SL:{fmt_precio(result['sl_limit'])}", "INFO")
            else:
                self.log(f"⚠️ {symbol} - Error actualizando OCO: {result.get('error', '?')}", "WARNING")
    
    def _ejecutar_compra(self, symbol, orden, config):
        """Ejecuta una orden de compra.
        DEMO: Simula compra internamente.
        REAL: Compra a MARKET en Binance + coloca OCO SELL."""
        try:
            analysis = orden.get('analysis', {})
            if not analysis:
                self.log(f"❌ {symbol} - No hay analysis en orden, no se puede comprar", "ERROR")
                return False
            
            tamano = calcular_tamano_posicion(config)
            if tamano <= 0:
                self.log(f"❌ {symbol} - Tamaño de posición es 0", "ERROR")
                return False
            
            es_modo_real = not config.get('modo_demo', True) and self.orders._is_configured()
            
            # Obtener valores originales
            valores_orig = orden.get('valores_originales', {})
            p1_orig = valores_orig.get('p1', analysis.get('punto_1', {}).get('price', 0))
            p0_orig = valores_orig.get('p0', analysis.get('punto_0', {}).get('price', 0))
            tp_orig = valores_orig.get('tp', analysis.get('precio_tp', 0))
            
            p1_fecha = analysis.get('punto_1', {}).get('time')
            p0_fecha = analysis.get('punto_0', {}).get('time')
            
            if es_modo_real:
                # === MODO REAL: Compra a MARKET en Binance ===
                # (Este caso solo ocurre como fallback si no había LIMIT BUY)
                try:
                    precio_actual = self.market.get_current_price(symbol)
                except:
                    precio_actual = 0
                if precio_actual <= 0:
                    self.log(f"❌ {symbol} - No se pudo obtener precio actual", "ERROR")
                    return False
                
                cantidad = tamano / precio_actual
                adj_qty = self.orders._adjust_quantity(cantidad, symbol)
                
                # Comprar a mercado
                result = self.orders.place_market_sell  # Error - should be market buy
                # Binance no tiene place_market_buy separado, usamos LIMIT con precio alto
                # Mejor: usamos la misma API de orden
                import hmac, hashlib
                params = {
                    'symbol': symbol,
                    'side': 'BUY',
                    'type': 'MARKET',
                    'quoteOrderQty': f"{tamano:.2f}",  # Comprar por X USDC
                }
                signed = self.orders._sign_request(params)
                url = f"https://api.binance.com/api/v3/order?{signed}"
                response = requests.post(url, headers=self.orders._headers(), timeout=10)
                data = response.json()
                
                if response.status_code == 200:
                    fills = data.get('fills', [])
                    if fills:
                        total_qty = sum(float(f['qty']) for f in fills)
                        total_cost = sum(float(f['qty']) * float(f['price']) for f in fills)
                        precio_compra = total_cost / total_qty if total_qty > 0 else 0
                    else:
                        total_qty = float(data.get('executedQty', 0))
                        cumm = float(data.get('cummulativeQuoteQty', 0))
                        precio_compra = cumm / total_qty if total_qty > 0 else 0
                    
                    self.log(f"💰 {symbol} - MARKET BUY ejecutada @ {fmt_precio(precio_compra)} | Qty:{total_qty:.6f}", "SUCCESS")
                    
                    self.open_positions[symbol] = {
                        'symbol': symbol,
                        'timeframe': orden.get('timeframe', '1h'),
                        'cantidad': total_qty,
                        'precio_entrada_real': precio_compra,
                        'fecha_entrada': datetime.utcnow().isoformat(),
                        'p1_suelo': p1_orig,
                        'p1_fecha': p1_fecha,
                        'p0_maximo': p0_orig,
                        'p0_fecha': p0_fecha,
                        'analysis': analysis,
                        'valores_originales': valores_orig,
                        'score': orden.get('score', 0),
                        'detalles_score': orden.get('detalles_score', {}),
                        'modo': 'REAL'
                    }
                    
                    if symbol in self.ordenes_pendientes:
                        self._eliminar_orden_pendiente(symbol)
                    
                    # Colocar OCO SELL
                    sl_definitivo = valores_orig.get('sl_definitivo', 0)
                    sl_trigger = valores_orig.get('sl_trigger', sl_definitivo * 1.002)
                    if tp_orig > 0 and sl_definitivo > 0:
                        oco_result = self.orders.place_oco_sell(symbol, total_qty, tp_orig, sl_trigger, sl_definitivo)
                        if oco_result.get('success'):
                            self.open_positions[symbol]['binance_oco_id'] = oco_result['orderListId']
                            self.log(f"🛡️ {symbol} - OCO SELL: TP:{fmt_precio(oco_result['tp_price'])} | SL:{fmt_precio(oco_result['sl_limit'])}", "SUCCESS")
                        else:
                            self.log(f"⚠️ {symbol} - OCO falló: {oco_result.get('error', '?')}", "WARNING")
                    
                    beneficio_esp = ((tp_orig - precio_compra) / precio_compra) * 100 if precio_compra > 0 else 0
                    self.log(f"🟢 COMPRA: {symbol} @ {fmt_precio(precio_compra)} | P1:{fmt_precio(p1_orig)} → P0:{fmt_precio(p0_orig)} | TP:{fmt_precio(tp_orig)} | +{beneficio_esp:.1f}%", "SUCCESS")
                    
                    if config.get('telegram_bot_token') and config.get('telegram_chat_id'):
                        msg = f"🟢 COMPRA REAL {symbol}\n💰 Precio: {fmt_precio(precio_compra)}\n🛡️ OCO colocada"
                        enviar_telegram(config['telegram_bot_token'], config['telegram_chat_id'], msg, config, 'compra')
                    
                    return True
                else:
                    self.log(f"❌ {symbol} - MARKET BUY falló: {data.get('msg', 'Error')}", "ERROR")
                    return False
            
            else:
                # === MODO DEMO: Simular compra ===
                try:
                    precio_compra = self.market.get_current_price(symbol)
                except:
                    precio_compra = 0
                
                if precio_compra <= 0:
                    precio_compra = analysis.get('precio_actual', 0)
                
                if precio_compra <= 0:
                    self.log(f"❌ {symbol} - Precio de compra es 0, abortando", "ERROR")
                    return False
                
                cantidad = tamano / precio_compra
                
                self.open_positions[symbol] = {
                    'symbol': symbol,
                    'timeframe': orden.get('timeframe', '1h'),
                    'cantidad': cantidad,
                    'precio_entrada_real': precio_compra,
                    'fecha_entrada': datetime.utcnow().isoformat(),
                    'p1_suelo': p1_orig,
                    'p1_fecha': p1_fecha,
                    'p0_maximo': p0_orig,
                    'p0_fecha': p0_fecha,
                    'analysis': analysis,
                    'valores_originales': valores_orig,
                    'score': orden.get('score', 0),
                    'detalles_score': orden.get('detalles_score', {}),
                    'modo': 'DEMO'
                }
                
                if symbol in self.ordenes_pendientes:
                    self._eliminar_orden_pendiente(symbol)
                
                beneficio_esp = ((tp_orig - precio_compra) / precio_compra) * 100 if precio_compra > 0 else 0
                self.log(f"🟢 COMPRA: {symbol} @ {fmt_precio(precio_compra)} | P1:{fmt_precio(p1_orig)} → P0:{fmt_precio(p0_orig)} | TP:{fmt_precio(tp_orig)} | +{beneficio_esp:.1f}%", "SUCCESS")
                
                if config.get('telegram_bot_token') and config.get('telegram_chat_id'):
                    msg = f"🟢 COMPRA {symbol}\n💰 Precio: {fmt_precio(precio_compra)}\n📊 Cantidad: {cantidad:.4f}"
                    enviar_telegram(config['telegram_bot_token'], config['telegram_chat_id'], msg, config, 'compra')
                
                return True
                
        except Exception as e:
            self.log(f"❌ {symbol} - Error ejecutando compra: {str(e)}", "ERROR")
            return False
    
    def _cerrar_posicion(self, symbol, motivo, config):
        """Cierra una posición.
        DEMO: Solo registra resultado.
        REAL: Cancela OCO + MARKET SELL en Binance."""
        if symbol not in self.open_positions:
            return
        
        posicion = self.open_positions[symbol]
        analysis = posicion.get('analysis', {})
        es_modo_real = posicion.get('modo') == 'REAL' and self.orders._is_configured()
        
        # === MODO REAL: Cancelar OCO y vender a mercado ===
        precio_venta_real = 0
        if es_modo_real:
            cantidad = posicion.get('cantidad', 0)
            
            # Cancelar OCO si existe
            oco_id = posicion.get('binance_oco_id')
            if oco_id:
                try:
                    # Verificar si OCO ya fue ejecutada por Binance
                    oco_status = self.orders.get_oco_status(symbol, oco_id)
                    list_status = ''
                    if oco_status:
                        list_status = oco_status.get('listOrderStatus') or oco_status.get('listStatusType', '')
                    
                    if list_status == 'ALL_DONE':
                        # OCO ya ejecutada → buscar precio de ejecución
                        sub_orders = oco_status.get('orderReports', oco_status.get('orders', []))
                        for order_info in sub_orders:
                            order_id = order_info.get('orderId')
                            if order_id:
                                order_detail = self.orders.get_order_status(symbol, order_id)
                                if order_detail and order_detail.get('status') == 'FILLED':
                                    precio_venta_real = float(order_detail.get('price', 0))
                                    self.log(f"📌 {symbol} - OCO ejecutada por Binance @ {fmt_precio(precio_venta_real)}", "INFO")
                                    break
                    else:
                        # OCO aún activa → cancelar
                        self.orders.cancel_oco(symbol, oco_id)
                except Exception as e:
                    self.log(f"⚠️ {symbol} - Error verificando OCO: {str(e)[:60]}", "WARNING")
                    try:
                        self.orders.cancel_oco(symbol, oco_id)
                    except:
                        pass
            
            # Si OCO no se ejecutó, vender a mercado
            if precio_venta_real <= 0 and cantidad > 0:
                # CRÍTICO: Usar balance REAL de Binance, no el almacenado
                # (la cantidad almacenada puede ser mayor por fees de compra)
                quote = config.get('pares_trading', ['USDC'])[0]
                asset = symbol.replace(quote, '')
                balances = self.orders.get_all_balances(min_value_usdc=0)
                if balances and asset in balances:
                    free_bal = balances[asset].get('free', 0)
                    locked_bal = balances[asset].get('locked', 0)
                    
                    # Si tokens están locked (orden SELL existente), no intentar MARKET SELL
                    if locked_bal > 0 and free_bal < locked_bal * 0.1:
                        self.log(f"⚠️ {symbol} - Tokens locked en orden SELL ({locked_bal:.4f} locked). No se puede vender a mercado.", "WARNING")
                        posicion['_venta_fallida'] = True
                        posicion['_venta_fallida_motivo'] = motivo
                        return
                    
                    if 0 < free_bal < cantidad:
                        self.log(f"📊 {symbol} - Ajustando qty: {cantidad} → {free_bal} (fees Binance)", "INFO")
                        cantidad = free_bal
                    elif free_bal <= 0:
                        self.log(f"⚠️ {symbol} - Sin balance libre para vender.", "WARNING")
                        posicion['_venta_fallida'] = True
                        posicion['_venta_fallida_motivo'] = motivo
                        return
                
                result = self.orders.place_market_sell(symbol, cantidad)
                if result.get('success'):
                    precio_venta_real = result.get('avg_price', 0)
                    self.log(f"💰 {symbol} - MARKET SELL ejecutada @ {fmt_precio(precio_venta_real)}", "INFO")
                else:
                    self.log(f"❌ {symbol} - MARKET SELL falló: {result.get('error', '?')}", "ERROR")
                    # CRÍTICO: NO continuar si la venta real falló - los tokens siguen en Binance
                    self.log(f"⚠️ {symbol} - Posición CONSERVADA (tokens siguen en Binance). Se reintentará en próximo ciclo.", "WARNING")
                    posicion['_venta_fallida'] = True
                    posicion['_venta_fallida_motivo'] = motivo
                    return
        
        # Obtener precio actual (real o simulado)
        if precio_venta_real > 0:
            precio_actual = precio_venta_real
        else:
            try:
                precio_fresco = self.market.get_current_price(symbol)
                if precio_fresco > 0:
                    precio_actual = precio_fresco
                else:
                    precio_actual = analysis.get('precio_actual', 0)
            except:
                precio_actual = analysis.get('precio_actual', 0)
        
        precio_entrada = posicion.get('precio_entrada_real', 0)
        cantidad = posicion.get('cantidad', 0)
        
        if precio_entrada > 0:
            beneficio_pct = ((precio_actual - precio_entrada) / precio_entrada) * 100
            beneficio_usd = (precio_actual - precio_entrada) * cantidad
        else:
            beneficio_pct = 0
            beneficio_usd = 0
        
        # Obtener P0 y P1 del análisis o de la posición
        p1_suelo = posicion.get('p1_suelo', analysis.get('punto_1', {}).get('price', 0))
        p0_maximo = posicion.get('p0_maximo', analysis.get('punto_0', {}).get('price', 0))
        p1_fecha = posicion.get('p1_fecha', analysis.get('punto_1', {}).get('time'))
        p0_fecha = posicion.get('p0_fecha', analysis.get('punto_0', {}).get('time'))
        temporalidad = posicion.get('timeframe', 'N/A')
        
        # Registrar estadísticas (en try/except para que la posición se elimine siempre)
        try:
            self.stats.registrar_operacion(
                symbol=symbol,
                fecha_entrada=posicion.get('fecha_entrada', ''),
                fecha_salida=datetime.utcnow().isoformat(),
                precio_entrada=precio_entrada,
                precio_salida=precio_actual,
                beneficio_pct=beneficio_pct,
                beneficio_usd=beneficio_usd,
                tipo=posicion.get('modo', 'DEMO'),
                p1_suelo=p1_suelo,
                p0_maximo=p0_maximo,
                p1_fecha=p1_fecha,
                p0_fecha=p0_fecha,
                temporalidad=temporalidad
            )
        except Exception as e:
            self.log(f"⚠️ {symbol} - Error registrando estadísticas: {str(e)[:60]}", "WARNING")
        
        # Si fue pérdida, añadir a blacklist
        if beneficio_pct < 0:
            self.blacklist.añadir(symbol, precio_entrada, config)
        
        # Contar op ganadora para protección
        if self.modo_proteccion_activado and beneficio_pct > 0:
            self._ops_ganadoras_proteccion = getattr(self, '_ops_ganadoras_proteccion', 0) + 1
            self.log(f"📊 Protección: {self._ops_ganadoras_proteccion} op(s) ganadora(s) de {config.get('proteccion_ops_para_volver', 1)} necesaria(s)", "INFO")
        
        del self.open_positions[symbol]
        
        emoji = "🟢" if beneficio_pct >= 0 else "🔴"
        modo_tag = " [REAL]" if es_modo_real else ""
        self.log(f"{emoji} VENTA: {symbol}{modo_tag} | {beneficio_pct:+.2f}% | {motivo} | P1:{fmt_precio(p1_suelo)} → P0:{fmt_precio(p0_maximo)} | Entr:{fmt_precio(precio_entrada)} → Sal:{fmt_precio(precio_actual)} | ${beneficio_usd:.2f}", "SUCCESS" if beneficio_pct >= 0 else "WARNING")
        
        # Anti-crash: contar SLs que saltan en este ciclo
        if 'SL' in motivo or 'EMERGENCIA' in motivo:
            self._sl_hits_este_ciclo += 1
        
        # Notificar Telegram
        if config.get('telegram_bot_token') and config.get('telegram_chat_id'):
            msg = f"{emoji} VENTA{modo_tag} {symbol}\n💰 P&L: {beneficio_pct:+.2f}%\n📋 Motivo: {motivo}"
            enviar_telegram(config['telegram_bot_token'], config['telegram_chat_id'], msg, config, 'venta')
    
    def _evaluar_swaps_inteligentes(self, config, oportunidades):
        """Evalúa posibles swaps inteligentes"""
        if not config.get('swap_automatico', False):
            return []
        
        swaps = []
        min_diferencia = config.get('swap_min_score_diferencia', 15.0)
        max_ganancia = config.get('swap_min_ganancia_actual', 50.0)
        
        for symbol, posicion in self.open_positions.items():
            # No intentar swap de posiciones con venta fallida
            if posicion.get('_venta_fallida'):
                continue
            
            score_actual = posicion.get('score', 0)
            analysis = posicion.get('analysis', {})
            precio_entrada = posicion.get('precio_entrada_real', 0)
            precio_actual = analysis.get('precio_actual', 0)
            
            if precio_entrada > 0 and precio_actual > 0:
                ganancia_actual = ((precio_actual - precio_entrada) / precio_entrada) * 100
            else:
                ganancia_actual = 0
            
            # Solo swap si no hemos ganado mucho
            if ganancia_actual > max_ganancia:
                continue
            
            for op in oportunidades:
                if op['symbol'] == symbol:
                    continue
                if op['symbol'] in self.open_positions:
                    continue
                # No swapear a moneda que ya tiene orden pendiente
                if op['symbol'] in self.ordenes_pendientes:
                    continue
                
                diferencia_score = op['score'] - score_actual
                if diferencia_score >= min_diferencia:
                    swaps.append({
                        'vender': symbol,
                        'comprar': op['symbol'],
                        'diferencia_score': diferencia_score,
                        'ganancia_actual': ganancia_actual,
                        'nuevo_score': op['score'],
                        'nueva_oportunidad': op
                    })
        
        swaps.sort(key=lambda x: x['diferencia_score'], reverse=True)
        return swaps
    
    def _ejecutar_swap(self, swap, config):
        """Ejecuta un swap"""
        symbol_vender = swap['vender']
        symbol_comprar = swap['comprar']
        
        self.log(f"🔄 SWAP: {symbol_vender} → {symbol_comprar}", "INFO")
        
        # Verificar que la posición a vender no tiene tokens locked (ya tiene SELL order)
        quote = config.get('pares_trading', ['USDC'])[0]
        asset_vender = symbol_vender.replace(quote, '')
        try:
            balances = self.orders.get_all_balances(min_value_usdc=0)
            if balances and asset_vender in balances:
                locked = balances[asset_vender].get('locked', 0)
                free = balances[asset_vender].get('free', 0)
                if locked > free * 5:
                    # Tokens están locked en una orden SELL existente → no intentar vender
                    self.log(f"⚠️ {symbol_vender} - Tokens locked en orden existente ({locked:.2f} locked vs {free:.4f} free). Swap cancelado.", "WARNING")
                    return
        except:
            pass
        
        # Cerrar posición actual
        self._cerrar_posicion(symbol_vender, 'SWAP', config)
        
        # CRÍTICO: Solo crear nueva orden si la venta realmente se ejecutó
        # Si la posición sigue en open_positions, la venta falló
        if symbol_vender in self.open_positions:
            self.log(f"⚠️ SWAP: {symbol_vender} no se pudo vender → {symbol_comprar} NO se crea", "WARNING")
            return
        
        # CHECK MAX ORDENES
        max_pos = config.get('max_positions', 5)
        total_activas = len(self.open_positions) + len(self.ordenes_pendientes)
        if total_activas >= max_pos:
            self.log(f"⚠️ SWAP: Límite de {max_pos} órdenes alcanzado → {symbol_comprar} a cola", "WARNING")
            return
        
        # Crear nueva orden
        op = swap['nueva_oportunidad']
        analysis = op['analysis']
        self.ordenes_pendientes[symbol_comprar] = {
            'symbol': symbol_comprar,
            'timeframe': op['timeframe'],
            'analysis': analysis,
            'score': op['score'],
            'detalles_score': op.get('detalles_score', {}),
            'timestamp_creacion': datetime.now(),
            'precio_entrada': analysis['precio_entrada'],
            'valores_originales': {
                'p1': analysis.get('punto_1', {}).get('price', 0),
                'p0': analysis.get('punto_0', {}).get('price', 0),
                'p1_time': analysis.get('punto_1', {}).get('time'),
                'p0_time': analysis.get('punto_0', {}).get('time'),
                'entrada': analysis.get('precio_entrada', 0),
                'tp': analysis.get('precio_tp', 0),
                'sl_trigger': analysis.get('precio_sl_trigger', 0),
                'sl_definitivo': analysis.get('precio_sl_definitivo', 0),
                'beneficio_pct': analysis.get('beneficio_esperado_pct', 0),
                'patron': analysis.get('patron_recuperacion', ''),
                'score': op['score'],
            }
        }
        
        # MODO REAL: Colocar LIMIT BUY en Binance
        if not config.get('modo_demo', True) and self.orders._is_configured():
            self._colocar_limit_buy_binance(symbol_comprar, self.ordenes_pendientes[symbol_comprar], config)
        
        self.stats.estadisticas['swaps_realizados'] += 1

# ============================================
# SINGLETON DEL BOT
# ============================================

_bot_instance = None
_bot_lock = threading.Lock()

# ============================================
# TELEGRAM BIDIRECCIONAL
# ============================================

class TelegramCommandHandler:
    """Maneja comandos de Telegram para controlar el bot remotamente.
    Comandos: /status /modo /cerrar /cancelar /posiciones /ordenes /ayuda"""
    
    def __init__(self, bot_instance):
        self.bot = bot_instance
        self._thread = None
        self._running = False
        self._last_update_id = 0
    
    def start(self):
        if self._running:
            return
        config = self.bot.config
        if not config.get('telegram_bot_token') or not config.get('telegram_chat_id'):
            return
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()
    
    def stop(self):
        self._running = False
    
    def _poll_loop(self):
        """Polling loop para recibir mensajes de Telegram"""
        while self._running:
            try:
                config = self.bot.config
                token = config.get('telegram_bot_token', '')
                chat_id = str(config.get('telegram_chat_id', ''))
                if not token or not chat_id:
                    time.sleep(10)
                    continue
                
                url = f"https://api.telegram.org/bot{token}/getUpdates"
                params = {'offset': self._last_update_id + 1, 'timeout': 15}
                resp = requests.get(url, params=params, timeout=20)
                
                if resp.status_code != 200:
                    time.sleep(5)
                    continue
                
                data = resp.json()
                for update in data.get('result', []):
                    self._last_update_id = update['update_id']
                    msg = update.get('message', {})
                    
                    # Solo responder a nuestro chat_id
                    if str(msg.get('chat', {}).get('id', '')) != chat_id:
                        continue
                    
                    text = msg.get('text', '').strip()
                    if text.startswith('/'):
                        self._process_command(text, token, chat_id)
                
            except Exception:
                time.sleep(5)
    
    def _send(self, token, chat_id, text):
        try:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            requests.post(url, json={'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML'}, timeout=5)
        except:
            pass
    
    def _process_command(self, text, token, chat_id):
        parts = text.split()
        cmd = parts[0].lower().split('@')[0]  # Remove @botname
        args = parts[1:] if len(parts) > 1 else []
        
        if cmd == '/status' or cmd == '/estado':
            self._cmd_status(token, chat_id)
        elif cmd == '/modo':
            self._cmd_modo(token, chat_id)
        elif cmd == '/posiciones' or cmd == '/pos':
            self._cmd_posiciones(token, chat_id)
        elif cmd == '/ordenes' or cmd == '/ord':
            self._cmd_ordenes(token, chat_id)
        elif cmd == '/cerrar':
            self._cmd_cerrar(token, chat_id, args)
        elif cmd == '/cancelar':
            self._cmd_cancelar(token, chat_id, args)
        elif cmd == '/ayuda' or cmd == '/help':
            self._cmd_ayuda(token, chat_id)
        else:
            self._send(token, chat_id, "❓ Comando no reconocido. Usa /ayuda")
    
    def _cmd_status(self, token, chat_id):
        config = self.bot.config
        modo = "🛡️ PROTECCIÓN" if self.bot.modo_proteccion_activado else ("🎮 DEMO" if config.get('modo_demo', True) else "💰 REAL")
        n_pos = len(self.bot.open_positions)
        n_ord = len(self.bot.ordenes_pendientes)
        running = "✅ Activo" if self.bot.running else "🛑 Parado"
        
        lines = [f"🤖 <b>TradingBro Status</b>", f"Estado: {running}", f"Modo: {modo}",
                 f"Posiciones: {n_pos}", f"Órdenes: {n_ord}"]
        
        # Balance
        try:
            bal = get_binance_balance(config.get('binance_api_key',''), config.get('binance_api_secret',''))
            if bal is not None:
                lines.append(f"Saldo: {bal:.2f} USDC")
        except:
            pass
        
        self._send(token, chat_id, "\n".join(lines))
    
    def _cmd_modo(self, token, chat_id):
        nuevo = self.bot.toggle_modo()
        modo_str = "DEMO 🎮" if nuevo else "REAL 💰"
        self._send(token, chat_id, f"✅ Bot cambiado a {modo_str}")
    
    def _cmd_posiciones(self, token, chat_id):
        if not self.bot.open_positions:
            self._send(token, chat_id, "📭 Sin posiciones abiertas")
            return
        
        lines = ["📊 <b>Posiciones Abiertas</b>"]
        for sym, pos in self.bot.open_positions.items():
            entrada = pos.get('precio_entrada_real', 0)
            actual = pos.get('analysis', {}).get('precio_actual', 0)
            pnl = ((actual - entrada) / entrada * 100) if entrada > 0 and actual > 0 else 0
            emoji = "🟢" if pnl >= 0 else "🔴"
            modo = pos.get('modo', 'DEMO')
            lines.append(f"{emoji} {sym} [{modo}] | {pnl:+.2f}%")
        
        self._send(token, chat_id, "\n".join(lines))
    
    def _cmd_ordenes(self, token, chat_id):
        if not self.bot.ordenes_pendientes:
            self._send(token, chat_id, "📭 Sin órdenes pendientes")
            return
        
        lines = ["📋 <b>Órdenes Pendientes</b>"]
        for sym, ord_data in self.bot.ordenes_pendientes.items():
            precio = ord_data.get('precio_entrada', 0)
            en_binance = "📤" if ord_data.get('binance_order_id') else "⏳"
            lines.append(f"{en_binance} {sym} @ {fmt_precio(precio)}")
        
        self._send(token, chat_id, "\n".join(lines))
    
    def _cmd_cerrar(self, token, chat_id, args):
        if not args:
            self._send(token, chat_id, "Uso: /cerrar SOMIUSDC")
            return
        symbol = args[0].upper()
        if not symbol.endswith('USDC'):
            symbol += 'USDC'
        if self.bot.cerrar_posicion_manual(symbol):
            self._send(token, chat_id, f"✅ {symbol} cerrada")
        else:
            self._send(token, chat_id, f"❌ {symbol} no encontrada en posiciones")
    
    def _cmd_cancelar(self, token, chat_id, args):
        if not args:
            self._send(token, chat_id, "Uso: /cancelar SOMIUSDC")
            return
        symbol = args[0].upper()
        if not symbol.endswith('USDC'):
            symbol += 'USDC'
        if self.bot.cancelar_orden_manual(symbol):
            self._send(token, chat_id, f"✅ {symbol} orden cancelada")
        else:
            self._send(token, chat_id, f"❌ {symbol} no encontrada en órdenes")
    
    def _cmd_ayuda(self, token, chat_id):
        self._send(token, chat_id,
            "🤖 <b>Comandos TradingBro</b>\n\n"
            "/status - Estado del bot\n"
            "/modo - Cambiar DEMO ↔ REAL\n"
            "/posiciones - Ver posiciones abiertas\n"
            "/ordenes - Ver órdenes pendientes\n"
            "/cerrar SYMBOL - Cerrar posición\n"
            "/cancelar SYMBOL - Cancelar orden\n"
            "/ayuda - Este mensaje"
        )


def get_bot():
    """Devuelve la instancia singleton del bot"""
    global _bot_instance
    with _bot_lock:
        if _bot_instance is None:
            _bot_instance = TradingBot()
            # Iniciar handler de comandos Telegram
            _bot_instance._telegram_handler = TelegramCommandHandler(_bot_instance)
            _bot_instance._telegram_handler.start()
        return _bot_instance

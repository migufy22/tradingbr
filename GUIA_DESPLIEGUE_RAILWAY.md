# 🚀 Guía de Despliegue — TradingBro en Railway

## ¿Qué vas a conseguir?
- El bot corriendo 24/7 en internet, sin que tu PC esté encendida
- Panel de control accesible desde cualquier dispositivo con contraseña
- Bot_state.json y config guardados en disco persistente (sobreviven reinicios)
- API keys nunca subidas a GitHub — solo viven en las variables de Railway

---

## PASO 1 — Preparar la carpeta en tu PC

Crea una carpeta nueva llamada `tradingbro` y pon dentro estos ficheros:

```
tradingbro/
├── app.py           ← el que te di
├── bot_logic.py     ← el que te di
├── requirements.txt ← el que te di
├── Dockerfile       ← el que te di
├── railway.toml     ← el que te di
└── .gitignore       ← el que te di
```

⚠️ NO pongas config.json ni bot_state.json en la carpeta.
Las API keys van en Railway, no en GitHub.

---

## PASO 2 — Subir a GitHub

1. Abre **GitHub Desktop** (o la web de github.com)
2. Crea un repositorio nuevo llamado `tradingbro`
3. Marca **Private** (repositorio privado, importante)
4. Arrastra la carpeta con los ficheros al repositorio
5. Haz commit con mensaje "Initial deploy"
6. Pulsa **Push**

---

## PASO 3 — Crear cuenta en Railway

1. Ve a **railway.app**
2. Pulsa **Login with GitHub** (usa tu cuenta de GitHub)
3. Autoriza Railway a acceder a tus repositorios

---

## PASO 4 — Crear el proyecto en Railway

1. En el dashboard de Railway, pulsa **+ New Project**
2. Selecciona **Deploy from GitHub repo**
3. Elige el repositorio `tradingbro`
4. Railway detectará el Dockerfile automáticamente
5. Pulsa **Deploy Now**

El primer despliegue tardará 2-3 minutos mientras instala las dependencias.

---

## PASO 5 — Añadir el Volume persistente (¡CRÍTICO!)

Sin esto, si Railway reinicia el bot pierdes config.json y bot_state.json.

1. En tu proyecto de Railway, pulsa sobre el servicio `tradingbro`
2. Ve a la pestaña **Volumes**
3. Pulsa **+ Add Volume**
4. En "Mount Path" escribe exactamente: `/data`
5. Pulsa **Create**

Railway reiniciará el bot con el disco persistente montado en `/data`.

---

## PASO 6 — Configurar las variables de entorno (API keys)

1. En tu proyecto Railway, pestaña **Variables**
2. Añade estas variables una por una:

| Variable              | Valor                              |
|-----------------------|------------------------------------|
| `BINANCE_API_KEY`     | tu clave de API de Binance         |
| `BINANCE_API_SECRET`  | tu secreto de API de Binance       |
| `TELEGRAM_TOKEN`      | 8241246563:AAE7GwV8RJk4gZ0Mvu7BJfb03OO-2WtjaRM |
| `TELEGRAM_CHAT_ID`    | 526315962                          |
| `UI_PASSWORD`         | elige una contraseña segura (ej: TradingBro2026!) |
| `DATA_DIR`            | /data                              |
| `PORT`                | 8501                               |

3. Railway reiniciará el bot automáticamente al guardar.

---

## PASO 7 — Obtener la URL pública

1. En tu proyecto Railway, pestaña **Settings**
2. Sección **Domains** → pulsa **Generate Domain**
3. Railway te dará una URL tipo: `tradingbro-production.up.railway.app`

Abre esa URL en el navegador → verás la pantalla de contraseña → introduce la que pusiste en `UI_PASSWORD`.

---

## PASO 8 — Configuración inicial del bot

La primera vez que entres, el bot no tiene config guardada. Necesitas:

1. Ve a ⚙️ Configuración → APIs y Conexión
2. Aunque las API keys ya están en variables de entorno y funcionan,
   pulsa **Test Conexiones** para verificar que todo va bien
3. Configura el resto de parámetros (capital, temporalidades, etc.)
4. Pulsa **Guardar** — esto crea `config.json` en `/data`
5. Arranca el bot con el botón **▶️ INICIAR**

---

## Actualizar el bot cuando hagas cambios

Cuando tengas una versión nueva de `app.py` o `bot_logic.py`:

1. Copia los ficheros nuevos a la carpeta `tradingbro`
2. En GitHub Desktop: verás los cambios en rojo/verde
3. Escribe un mensaje de commit (ej: "Fix hold coins")
4. Pulsa **Commit** → **Push**
5. Railway detecta el push y redespliega automáticamente en ~2 min

---

## Precios estimados

| Concepto          | Coste aproximado |
|-------------------|-----------------|
| Plan Hobby        | ~5 $/mes         |
| Volume 1GB        | ~0.25 $/mes      |
| **Total**         | **~5.25 $/mes**  |

El plan gratuito solo da ~500 horas/mes. Para 24/7 necesitas Hobby (~5$).

---

## Diferencias entre local y Railway

| Característica     | Local (tu PC)      | Railway              |
|--------------------|--------------------|----------------------|
| Disponibilidad     | Solo cuando encendida | 24/7               |
| Coste              | 0€                 | ~5$/mes              |
| Velocidad setup    | Inmediata          | 15-20 min primera vez |
| API keys           | En config.json     | En variables de entorno |
| Estado bot         | Carpeta local      | Volume /data         |
| Logs               | Terminal           | Dashboard Railway    |
| Actualizar         | Copiar fichero     | Git push             |

---

## Si algo va mal

**El bot no arranca:** Ve a Railway → tu servicio → pestaña **Logs** → busca el error en rojo.

**Perdí la config al reiniciar:** Comprueba que el Volume está montado en `/data` y que `DATA_DIR=/data` está en Variables.

**No puedo acceder a la URL:** Comprueba que el puerto 8501 está abierto — en Railway Settings → Networking → puerto 8501 expuesto.

**Las API keys no funcionan:** Ve a Variables y verifica que no tienen espacios al principio o al final.

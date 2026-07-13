import makeWASocket, {
    useMultiFileAuthState,
    DisconnectReason,
    fetchLatestBaileysVersion
} from '@whiskeysockets/baileys'
import express from 'express'
import qrcode from 'qrcode-terminal'
import QRCode from 'qrcode'
import pino from 'pino'

const logger = pino({ level: 'silent' })
const app = express()
app.use(express.json())

// Auth session stored in AUTH_DIR (use Railway volume path in production)
const AUTH_DIR = process.env.AUTH_DIR || 'auth_info_baileys'
const PORT = process.env.PORT || 3001
const API_KEY = process.env.API_KEY || ''

// Simple API key guard — skip if API_KEY not set (local dev)
app.use((req, res, next) => {
    if (req.path === '/status') return next() // always allow health check
    if (API_KEY && req.headers['x-api-key'] !== API_KEY) {
        return res.status(401).json({ success: false, error: 'Unauthorized' })
    }
    next()
})

let sock = null
let isConnected = false
let lastQR = null

async function connectToWhatsApp() {
    const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR)
    const { version } = await fetchLatestBaileysVersion()

    sock = makeWASocket({
        version,
        auth: state,
        logger,
        printQRInTerminal: false,
        browser: ['DocRegistry Pro', 'Chrome', '1.0.0']
    })

    sock.ev.on('creds.update', saveCreds)

    sock.ev.on('connection.update', (update) => {
        const { connection, lastDisconnect, qr } = update

        if (qr) {
            lastQR = qr
            console.log('\n📱 Scan this QR code with your dedicated WhatsApp number:\n')
            qrcode.generate(qr, { small: true })
            console.log('\nOr visit GET /qr to get the QR code as a URL\n')
        }

        if (connection === 'open') {
            isConnected = true
            lastQR = null
            console.log('✅ WhatsApp connected successfully!')
        }

        if (connection === 'close') {
            isConnected = false
            const statusCode = lastDisconnect?.error?.output?.statusCode
            const shouldReconnect = statusCode !== DisconnectReason.loggedOut
            if (shouldReconnect) {
                console.log('🔄 Connection lost, reconnecting...')
                connectToWhatsApp()
            } else {
                console.log('❌ Logged out. Clear AUTH_DIR and restart to re-scan QR.')
            }
        }
    })
}

// Health check — no auth required
app.get('/status', (req, res) => {
    res.json({ connected: isConnected, qr_pending: !!lastQR })
})

// Serves QR code as a live HTML page with auto-refresh every 15 seconds
app.get('/qr', async (req, res) => {
    if (isConnected) {
        return res.send(`<!DOCTYPE html><html><body style="text-align:center;font-family:sans-serif;padding:40px">
            <h2>✅ WhatsApp Connected!</h2>
            <p>The Baileys service is linked and ready to send messages.</p>
        </body></html>`)
    }
    if (!lastQR) {
        return res.send(`<!DOCTYPE html><html><head><meta http-equiv="refresh" content="3"></head>
        <body style="text-align:center;font-family:sans-serif;padding:40px">
            <h2>⏳ Waiting for QR code...</h2>
            <p>Page refreshes automatically. Please wait.</p>
        </body></html>`)
    }
    try {
        const qrDataUrl = await QRCode.toDataURL(lastQR, { width: 300 })
        res.send(`<!DOCTYPE html>
        <html>
        <head>
            <title>DocRegistry Pro - WhatsApp QR</title>
            <meta http-equiv="refresh" content="15">
        </head>
        <body style="text-align:center;font-family:sans-serif;padding:40px;background:#f9f9f9">
            <h2>📱 Scan with WhatsApp — Act Fast!</h2>
            <p>Open WhatsApp → <b>Linked Devices</b> → <b>Link a Device</b> → Scan below</p>
            <img src="${qrDataUrl}" style="width:300px;height:300px;border:4px solid #25D366;border-radius:12px">
            <p style="color:#888;font-size:13px">⏱ QR expires in ~20 seconds. Page auto-refreshes every 15s.</p>
        </body>
        </html>`)
    } catch (err) {
        res.status(500).send('Error generating QR code: ' + err.message)
    }
})

// Send message to WhatsApp group
app.post('/send', async (req, res) => {
    const { group_id, message } = req.body

    if (!isConnected) {
        return res.status(503).json({ success: false, error: 'WhatsApp not connected. Check /status or /qr.' })
    }
    if (!group_id || !message) {
        return res.status(400).json({ success: false, error: 'group_id and message are required' })
    }

    try {
        await sock.sendMessage(group_id, { text: message })
        console.log(`✅ Message sent to group: ${group_id}`)
        res.json({ success: true })
    } catch (err) {
        console.error(`❌ Send failed: ${err.message}`)
        res.status(500).json({ success: false, error: err.message })
    }
})

app.listen(PORT, () => {
    console.log(`🚀 Baileys API running on port ${PORT}`)
    console.log(`🔑 API key protection: ${API_KEY ? 'enabled' : 'disabled (local dev mode)'}`)
    console.log('Connecting to WhatsApp...\n')
})

connectToWhatsApp()

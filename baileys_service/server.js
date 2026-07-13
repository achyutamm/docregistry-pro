import makeWASocket, {
    useMultiFileAuthState,
    DisconnectReason,
    fetchLatestBaileysVersion
} from '@whiskeysockets/baileys'
import express from 'express'
import qrcode from 'qrcode-terminal'
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

// Returns QR code as a scannable image URL (for Railway — no terminal access)
app.get('/qr', (req, res) => {
    if (isConnected) {
        return res.json({ connected: true, message: 'Already connected, no QR needed.' })
    }
    if (!lastQR) {
        return res.json({ connected: false, message: 'No QR available yet. Wait a few seconds and retry.' })
    }
    const qrImageUrl = `https://api.qrserver.com/v1/create-qr-code/?size=300x300&data=${encodeURIComponent(lastQR)}`
    res.json({ connected: false, qr_url: qrImageUrl })
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

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

let sock = null
let isConnected = false

async function connectToWhatsApp() {
    const { state, saveCreds } = await useMultiFileAuthState('auth_info_baileys')
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
            console.log('\n📱 Scan this QR code with your dedicated WhatsApp number:\n')
            qrcode.generate(qr, { small: true })
            console.log('\nWaiting for scan...\n')
        }

        if (connection === 'open') {
            isConnected = true
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
                console.log('❌ Logged out. Delete the auth_info_baileys folder and restart.')
            }
        }
    })
}

app.get('/status', (req, res) => {
    res.json({ connected: isConnected })
})

app.post('/send', async (req, res) => {
    const { group_id, message } = req.body

    if (!isConnected) {
        return res.status(503).json({ success: false, error: 'WhatsApp not connected' })
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

const PORT = 3001
app.listen(PORT, () => {
    console.log(`🚀 Baileys API running on http://localhost:${PORT}`)
    console.log('Connecting to WhatsApp...\n')
})

connectToWhatsApp()

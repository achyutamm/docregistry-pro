// Run this once to find your WhatsApp group ID.
// IMPORTANT: Stop server.js before running this.
// Usage: npm run list-groups

import makeWASocket, {
    useMultiFileAuthState,
    fetchLatestBaileysVersion,
    DisconnectReason
} from '@whiskeysockets/baileys'
import qrcode from 'qrcode-terminal'
import pino from 'pino'

const logger = pino({ level: 'silent' })

async function listGroups() {
    const { state, saveCreds } = await useMultiFileAuthState('auth_info_baileys')
    const { version } = await fetchLatestBaileysVersion()

    const sock = makeWASocket({
        version,
        auth: state,
        logger,
        browser: ['DocRegistry Pro', 'Chrome', '1.0.0']
    })

    sock.ev.on('creds.update', saveCreds)

    sock.ev.on('connection.update', async (update) => {
        const { connection, qr, lastDisconnect } = update

        if (qr) {
            console.log('\n📱 Scan this QR code with your dedicated WhatsApp number:\n')
            qrcode.generate(qr, { small: true })
        }

        if (connection === 'close') {
            const statusCode = lastDisconnect?.error?.output?.statusCode
            if (statusCode !== DisconnectReason.loggedOut) {
                console.log('Connection dropped, retrying...')
                listGroups()
            }
        }

        if (connection === 'open') {
            console.log('✅ Connected! Waiting for session to stabilise...\n')

            // Give WhatsApp time to fully sync before querying groups
            await new Promise(r => setTimeout(r, 6000))

            try {
                const groups = await sock.groupFetchAllParticipating()
                const groupList = Object.values(groups)

                if (groupList.length === 0) {
                    console.log('No groups found. Make sure this number is a member of at least one WhatsApp group.')
                } else {
                    console.log('='.repeat(55))
                    console.log('  YOUR WHATSAPP GROUPS')
                    console.log('='.repeat(55))
                    groupList.forEach((group, i) => {
                        console.log(`\n[${i + 1}] ${group.subject}`)
                        console.log(`    ID:      ${group.id}`)
                        console.log(`    Members: ${group.participants?.length || 0}`)
                    })
                    console.log('\n' + '='.repeat(55))
                    console.log('Copy the ID of your target group and paste it into')
                    console.log('config.yaml under whatsapp.group_id')
                    console.log('='.repeat(55))
                }
            } catch (err) {
                console.error('❌ Could not fetch groups:', err.message)
                console.log('\nTry again — make sure server.js is NOT running in another terminal.')
            }

            await sock.end()
            process.exit(0)
        }
    })
}

listGroups()

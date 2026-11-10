export type Lang = 'fr' | 'en'
export const T = {
  fr: {
    title: 'Pré-entretien', welcome: 'Bonjour', intro: 'Un court échange avec Camille, notre assistante IA, à la place de l\'appel de préqualification.',
    points: [
      ['⏱', 'Environ 10 minutes, quand vous voulez, depuis votre téléphone ou votre ordinateur.'],
      ['🤖', 'Camille est une IA. Elle pose des questions et ne décide de rien : c\'est un recruteur qui lit l\'échange et décide.'],
      ['📝', 'L\'échange est enregistré et transcrit pour le recruteur. Vous pouvez l\'arrêter à tout moment.'],
      ['✉️', 'Chaque candidat reçoit une réponse de l\'équipe de recrutement.'],
    ],
    consent: 'J\'ai compris et j\'accepte que cet échange soit enregistré, transcrit et lu par l\'équipe de recrutement du Groupe Orvane.',
    voice: 'Commencer l\'entretien vocal', text: 'Répondre par écrit', micTip: 'Votre navigateur vous demandera l\'accès au micro.',
    startCall: 'Démarrer', connecting: 'Connexion…', listening: 'Camille vous écoute', speaking: 'Camille parle', thinkingVoice: 'Camille réfléchit', muted: 'Micro coupé',
    micDenied: 'Le micro est bloqué. Autorisez-le dans votre navigateur, ou répondez par écrit.',
    typeHere: 'Écrivez votre réponse…', send: 'Envoyer', end: 'Terminer', thinking: 'Camille écrit…',
    doneTitle: 'Merci, c\'est terminé !', doneText: 'Le recruteur va lire votre échange. Vous recevrez une réponse de l\'équipe de recrutement du Groupe Orvane, quelle que soit la suite.',
    expired: 'Ce lien a expiré.', expiredText: 'La date limite du pré-entretien est dépassée. Contactez l\'équipe de recrutement du Groupe Orvane : elle vous enverra un nouveau lien.', validUntil: 'Lien valable jusqu\'au',
    invalid: 'Ce lien est invalide ou a expiré.', already: 'Cet entretien est déjà terminé. Merci !',
  },
  en: {
    title: 'Pre-interview', welcome: 'Hello', intro: 'A short conversation with Camille, our AI assistant, replacing the pre-qualification call.',
    points: [
      ['⏱', 'About 10 minutes, whenever suits you, on your phone or computer.'],
      ['🤖', 'Camille is an AI. She asks questions and decides nothing: a recruiter reads the conversation and decides.'],
      ['📝', 'The conversation is recorded and transcribed for the recruiter. You can stop at any time.'],
      ['✉️', 'Every candidate receives an answer from the recruiting team.'],
    ],
    consent: 'I understand and agree that this conversation is recorded, transcribed and read by the Groupe Orvane recruiting team.',
    voice: 'Start the voice interview', text: 'Answer in writing', micTip: 'Your browser will ask for microphone access.',
    startCall: 'Start', connecting: 'Connecting…', listening: 'Camille is listening', speaking: 'Camille is speaking', thinkingVoice: 'Camille is thinking', muted: 'Mic muted',
    micDenied: 'The microphone is blocked. Allow it in your browser, or answer in writing.',
    typeHere: 'Type your answer…', send: 'Send', end: 'Finish', thinking: 'Camille is typing…',
    doneTitle: 'Thank you, all done!', doneText: 'A recruiter will read your conversation. You will receive an answer from the Groupe Orvane recruiting team, whatever the outcome.',
    expired: 'This link has expired.', expiredText: 'The deadline for this pre-interview has passed. Please contact the Groupe Orvane recruiting team: they will send you a new link.', validUntil: 'Link valid until',
    invalid: 'This link is invalid or has expired.', already: 'This interview is already finished. Thank you!',
  },
} as const

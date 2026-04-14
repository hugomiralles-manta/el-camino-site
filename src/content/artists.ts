export const artists = [
  {
    id: 'elisabeth',
    name: 'Elisabeth von Buxhoeveden',
    roles: ['chant', 'jeu', 'idée originale', 'texte', 'mise en scène'],
    tagline: 'La marcheuse, c\'est elle.',
    bio: `Elle est aussi chanteuse, comédienne, metteuse en scène, rêveuse, blonde et insomniaque.
Le théâtre lui colle à la peau, elle se brosse les dents en chantant et n'arrive pas à devenir végétarienne pour de vrai.
Elle se réconforte avec un bon livre et s'instruit avec du chocolat. Pour elle, une journée sans rire, ça n'existe pas.`,
    photo: 'images/elisabeth.jpg',
  },
  {
    id: 'jean-marc',
    name: 'Jean-Marc Miralles',
    roles: ['musique', 'chant', 'jeu', 'composition'],
    tagline: 'Le musicien, c\'est lui.',
    bio: `Il est aussi compositeur, chanteur, comédien, ronchon, pied-noir et lève-tôt.
Le blues lui colle à la peau, il épluche les carottes en battant la mesure et n'arrive pas à faire la grasse mat pour de vrai.
Il écoute du yoga et se maintient en forme avec Eric Clapton. Pour lui, une journée sans corde à gratter n'est pas une bonne journée.`,
    photo: 'images/jean-marc.jpg',
  },
  {
    id: 'karine',
    name: 'Karine Darcos',
    roles: ['paroles', 'dramaturgie'],
    tagline: 'La plume, c\'est elle.',
    bio: `Elle est aussi traductrice, correctrice, idéaliste, brune et tyrannique (mais c'est pour leur bien !).
Les mots lui collent à la peau, elle boit son café en allemand et n'arrive pas à arrêter le chocolat pour de vrai.
Elle se réconforte avec un bon livre et s'instruit avec de la science-fiction.
Pour elle, une journée sans rêver n'est pas une bonne journée.`,
    photo: 'images/karine.jpg',
  },
] as const;

export const creativeTeam = [
  { role: 'Idée originale, texte et interprétation', person: 'Elisabeth von Buxhoeveden' },
  { role: 'Composition, musique et interprétation', person: 'Jean-Marc Miralles' },
  { role: 'Paroles et dramaturgie', person: 'Karine Darcos' },
  { role: 'Collaboration artistique', person: 'Maud Landau' },
  { role: 'Création lumière', person: 'Jean-Louis Racoillet' },
] as const;

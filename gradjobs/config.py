"""Réglages du scraper. Tout ce que tu veux ajuster est ici."""

USER_AGENT = "gradjobs/1.0 (personal job-search tool; public ATS job-board APIs)"

# --- Niveau demandé ----------------------------------------------------------
# Une offre est rejetée si sa description exige plus d'années d'expérience que ça.
MAX_YEARS_REQUIRED = 2
# Stages / alternance / Werkstudent : exclus par défaut (tu cherches un premier CDI).
INCLUDE_INTERNSHIPS = False
# Titre neutre ("Software Engineer") sans aucun signal débutant dans la description :
# False = on rejette (précision), True = on garde (rappel).
INCLUDE_UNSPECIFIED_LEVEL = False
# Ignorer les offres dont la date de publication (quand elle est connue) dépasse ça.
MAX_POSTING_AGE_DAYS = 90
# Une offre disparue reste affichée 🔒 pendant ce nombre de jours, puis est retirée.
CLOSED_KEEP_DAYS = 7
# Un slug qui répond 404 n'est pas re-testé avant ce délai.
INVALID_RECHECK_DAYS = 14

# --- Régions -----------------------------------------------------------------
# (nom, emoji, motif). L'ordre compte : la première région qui matche gagne.
# Les motifs évitent les faux amis (London, ON / Dublin, CA / Cambridge, MA...).
REGIONS = [
    ("Switzerland", "🇨🇭",
     r"switzerland|schweiz|suisse|svizzera|zurich|zürich|"
     r"geneva(?!,?\s*(?:il|ny|oh|illinois|new york)\b)|genève|geneve|lausanne|basel|bern\b|berne\b|"
     r"zug\b|lugano|winterthur|neuch[âa]tel|schlieren|lucerne|luzern|st\.? gallen|fribourg|thalwil|"
     r"cheseaux|prilly|renens|ecublens|dübendorf|dubendorf"),
    ("Netherlands", "🇳🇱",
     r"netherlands|nederland|amsterdam|rotterdam|utrecht|eindhoven|the hague|den haag|delft|"
     r"groningen|breda|leiden|haarlem|amersfoort|nijmegen|tilburg|enschede|maastricht|almere|"
     r"zwolle|hengelo|veldhoven|'s-hertogenbosch"),
    ("Canada", "🇨🇦",
     r"canada|toronto|vancouver(?!,?\s*(?:wa|washington)\b)|montr[ée]al|ottawa|calgary|edmonton|"
     r"waterloo(?!,?\s*(?:ia|iowa|il)\b)|kitchener|quebec|québec|mississauga|winnipeg|halifax|"
     r"burnaby|markham|(?-i:,\s*(?:ON|BC|AB|QC|MB|NS|NB|SK)\b)"),
    ("United Kingdom", "🇬🇧",
     r"united kingdom|\buk\b|great britain|england|scotland|wales|northern ireland|"
     r"london(?!,?\s*(?:on\b|ontario|canada))|manchester(?!,?\s*(?:nh|ct|new hampshire)\b)|"
     r"edinburgh|glasgow|cambridge(?!,?\s*(?:ma|mass|massachusetts|on|ontario)\b)|"
     r"oxford(?!,?\s*(?:ms|oh|mississippi|ohio)\b)|bristol|birmingham(?!,?\s*(?:al|alabama)\b)|"
     r"leeds|sheffield|nottingham|cardiff|belfast|liverpool|southampton|milton keynes|leicester"),
    ("Singapore", "🇸🇬", r"singapore"),
    ("Hong Kong", "🇭🇰",
     r"hong kong|hk\b|hongkong"),
    ("Taiwan", "🇹🇼",
     r"taiwan|taipei|taichung|kaohsiung|tainan|hsinchu"),
    ("Germany", "🇩🇪",
     r"germany|deutschland|berlin|munich|münchen|munchen|hamburg|frankfurt|cologne|köln|koln|"
     r"stuttgart|düsseldorf|dusseldorf|dresden|karlsruhe|leipzig|nuremberg|nürnberg|hannover|"
     r"bonn\b|aachen|darmstadt|walldorf|heidelberg|freiburg|potsdam|baden-w[üu]rttemberg|bavaria|bayern"),
    ("Ireland", "🇮🇪",
     r"(?<!northern )ireland|dublin(?!,?\s*(?:ca|oh|ga|tx|california|ohio|georgia)\b)|cork\b|"
     r"galway|limerick|waterford"),
    ("Nordics", "🇸🇪",
     r"sweden|sverige|stockholm|gothenburg|göteborg|goteborg|malmö|malmo|uppsala|norway|norge|oslo|"
     r"bergen|trondheim|stavanger|denmark|danmark|copenhagen|københavn|aarhus|odense|finland|suomi|"
     r"helsinki|espoo|tampere|oulu|iceland|reykjavik"),
    ("Remote (Europe)", "🌍",
     r"remote.{0,30}(?:europe|emea|\beu\b|european|eea)|(?:europe|emea|\beu\b|european|eea).{0,30}remote|"
     r"anywhere in europe"),
     ("France", "🇫🇷",
      r"paris(?!,?\s*(?:tx|texas|ky|kentucky|tn|tennessee|on\b|ontario|il|illinois|id|idaho|"
      r"me|maine|mo|missouri)\b)|\bparis,?\s*france\b"),
]

# Régions réellement affichées. Retire-en / ajoute-en selon ta recherche.
# (France volontairement absente : tu cherches hors de France.)
ENABLED_REGIONS = {
    "Netherlands", "Switzerland", "United Kingdom", "Canada",  "Singapore",
    "Hong Kong", "Taiwan", "Germany", "Ireland", "Nordics", "Remote (Europe)", "France"
}

# --- Sources de découverte des entreprises ----------------------------------
# Listes de slugs par ATS, construites à partir de l'index Common Crawl par le projet
# Feashliaa/job-board-aggregator. Code MIT ; jeux de données sous CC BY-NC 4.0
# (usage non commercial, attribution obligatoire) : téléchargés à l'exécution, jamais
# recopiés dans ce dépôt.
SLUG_LIST_URLS = {
    "greenhouse": "https://raw.githubusercontent.com/Feashliaa/job-board-aggregator/main/data/greenhouse_companies.json",
    "lever":      "https://raw.githubusercontent.com/Feashliaa/job-board-aggregator/main/data/lever_companies.json",
    "ashby":      "https://raw.githubusercontent.com/Feashliaa/job-board-aggregator/main/data/ashby_companies.json",
}
SLUG_LIST_MAX_AGE_DAYS = 7

# Si plus de cette part des boards répondent par une ERREUR (réseau, 429, 5xx ; les 404 ne comptent pas),
# le run est considéré comme non fiable : il échoue et n'écrit RIEN (pas de README vide/tronqué publié).
MAX_ERROR_RATE = 0.5

# --- Politesse réseau --------------------------------------------------------
# Threads par ATS (Ashby est le plus restrictif).
WORKERS = {"greenhouse": 20, "lever": 20, "ashby": 5}

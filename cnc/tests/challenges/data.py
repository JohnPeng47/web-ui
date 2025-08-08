from .vulnerability import Vulnerability

JUICESHOP_AUTHNZ_CHALLENGES_FULL = {
    "brokenAuth": [
        Vulnerability(id=6, key="resetPasswordBjoernOwaspChallenge", name="Bjoern's Favorite Pet"),
        Vulnerability(id=14, key="changePasswordBenderChallenge", name="Change Bender's Password"),
        Vulnerability(id=37, key="ghostLoginChallenge", name="GDPR Data Erasure"),
        Vulnerability(id=47, key="oauthUserPasswordChallenge", name="Login Bjoern"),
        Vulnerability(id=50, key="loginSupportChallenge", name="Login Support Team"),
        Vulnerability(id=59, key="weakPasswordChallenge", name="Password Strength"),
        Vulnerability(id=67, key="resetPasswordBenderChallenge", name="Reset Bender's Password"),
        Vulnerability(id=68, key="resetPasswordBjoernChallenge", name="Reset Bjoern's Password"),
        Vulnerability(id=69, key="resetPasswordJimChallenge", name="Reset Jim's Password"),
        Vulnerability(id=70, key="resetPasswordMortyChallenge", name="Reset Morty's Password"),
        Vulnerability(id=80, key="twoFactorAuthUnsafeSecretStorageChallenge", name="Two Factor Authentication"),
        Vulnerability(id=100, key="resetPasswordUvoginChallenge", name="Reset Uvogin's Password"),
        Vulnerability(id=101, key="geoStalkingMetaChallenge", name="Meta Geo Stalking"),
        Vulnerability(id=102, key="geoStalkingVisualChallenge", name="Visual Geo Stalking")
    ],
    "brokenAccessControl": [
        Vulnerability(id=3, key="registerAdminChallenge", name="Admin Registration"),
        Vulnerability(id=11, key="web3SandboxChallenge", name="Web3 Sandbox"),
        Vulnerability(id=22, key="easterEggLevelOneChallenge", name="Easter Egg"),
        Vulnerability(id=29, key="feedbackChallenge", name="Five-Star Feedback"),
        Vulnerability(id=31, key="forgedFeedbackChallenge", name="Forged Feedback"),
        Vulnerability(id=32, key="forgedReviewChallenge", name="Forged Review"),
        Vulnerability(id=38, key="dataExportChallenge", name="GDPR Data Theft"),
        Vulnerability(id=51, key="basketManipulateChallenge", name="Manipulate Basket"),
        Vulnerability(id=64, key="changeProductChallenge", name="Product Tampering"),
        Vulnerability(id=72, key="ssrfChallenge", name="SSRF"),
        Vulnerability(id=86, key="basketAccessChallenge", name="View Basket"),
        Vulnerability(id=98, key="csrfChallenge", name="CSRF")
    ],
    "jwt": [
        Vulnerability(id=33, key="jwtForgedChallenge", name="Forged Signed JWT"),
        Vulnerability(id=81, key="jwtUnsignedChallenge", name="Unsigned JWT")
    ]
}

JUICESHOP_AUTHNZ_CHALLENGES_TEST = {
    "brokenAccessControl": [
        Vulnerability(id=86, key="basketAccessChallenge", name="View Basket"),
    ],
}

JUICESHOP_AUTHNZ_CHALLENGES_DEMO = {
    "brokenAccessControl": [
        Vulnerability(id=51, key="basketManipulateChallenge", name="Manipulate Basket"),
        Vulnerability(id=86, key="basketAccessChallenge", name="View Basket"),
        Vulnerability(id=32, key="forgedReviewChallenge", name="Forged Review"),
        Vulnerability(id=29, key="feedbackChallenge", name="Five-Star Feedback"),
        Vulnerability(id=31, key="forgedFeedbackChallenge", name="Forged Feedback"),
        Vulnerability(id=64, key="changeProductChallenge", name="Product Tampering"),
        Vulnerability(id=4, key="adminSectionChallenge", name="Admin Section"),
    ],
}

USERS = [
    {
        "username": "bjoern@juice-sh.op",
        "email": "bjoern@juice-sh.op",
        "role": "admin",
        "password": "monkey summer birthday are all bad passwords but work just fine in a long passphrase"
    },
    {
        "username": "john@juice-sh.op",
        "email": "john@juice-sh.op",
        "role": "customer",
        "password": "y&x5Z#f6W532Z4445#Ae2HkwZVyDb7&oCUaDzFU"
    },
    {
        "username": "jim@juice-sh.op",
        "email": "jim@juice-sh.op",
        "role": "customer",
        "password": "ncc-1701"
    }
]

def get_challenges(challenges):
    return [v for vuln in challenges.values() for v in vuln]
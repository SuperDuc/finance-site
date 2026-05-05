#!/usr/bin/env python3
"""
FinanceFlow Article Generator
Runs 3x/day via GitHub Actions — generates unique finance articles,
updates blog.html, and rebuilds sitemap.xml automatically.
"""

import json, os, random, re, html
from datetime import date, datetime
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError
import xml.etree.ElementTree as ET

# ── CONFIG ─────────────────────────────────────────────────────────────────────
TEMPLATE_PER_RUN = 2
NEWS_PER_RUN     = 1
SITE_ROOT        = Path(__file__).parent
ARTICLES_DIR     = SITE_ROOT / 'articles'
TRACKING_FILE    = SITE_ROOT / 'articles_published.json'
BLOG_FILE        = SITE_ROOT / 'blog.html'
INDEX_FILE       = SITE_ROOT / 'index.html'
SITEMAP_FILE     = SITE_ROOT / 'sitemap.xml'
SITE_URL         = 'https://financeflowguide.netlify.app'

TODAY = date.today().isoformat()
TS    = datetime.now().strftime('%H%M%S')

# ── AFFILIATE LINKS ─────────────────────────────────────────────────────────────
AFF = {
    'gemini':      {'name': 'Gemini Exchange',    'url': 'https://exchange.gemini.com/register?referral=v995pwas8&type=referral',                              'bonus': 'Get $50 free crypto when you trade $100',           'cta': 'Get $50 Free Crypto →'},
    'gemini_card': {'name': 'Gemini Credit Card', 'url': 'https://creditcard.exchange.gemini.com/credit-card/apply?referral_code=wywqe3gle',                  'bonus': 'Earn up to 4% back in crypto — no annual fee',      'cta': 'Apply — No Annual Fee →'},
    'strike':      {'name': 'Strike',             'url': 'http://invite.strike.me/120JJD',                                                                    'bonus': 'Your first $500 of Bitcoin is completely fee-free', 'cta': 'Get $0 Fees on Your First $500 of BTC →'},
    'robinhood':   {'name': 'Robinhood',          'url': 'http://join.robinhood.com/brianh-c9de06e',                                                          'bonus': 'You both get a free gift stock when you sign up',   'cta': 'Get Your Free Gift Stock →'},
    'coinbase':    {'name': 'Coinbase',           'url': 'https://coinbase.com/join/FYHUYXW?src=ios-link',                                                    'bonus': 'Sign up free — buy crypto in minutes',              'cta': 'Join Coinbase Free →'},
}

# ── HELPERS ────────────────────────────────────────────────────────────────────
def md(text):
    """Mini markdown: **bold**, line-breaks."""
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'\n\n', '</p><p>', text)
    text = re.sub(r'\n', '<br>', text)
    return text

def pick(lst):
    return random.choice(lst)

# ── RSS NEWS FETCHER ───────────────────────────────────────────────────────────
RSS_FEEDS = [
    'https://finance.yahoo.com/rss/topstories',
    'https://www.cnbc.com/id/100003114/device/rss/rss.html',
    'https://feeds.marketwatch.com/marketwatch/topstories/',
]

CRYPTO_RSS_FEEDS = [
    'https://cointelegraph.com/rss',
    'https://coindesk.com/arc/outboundfeeds/rss/',
]

NEWS_AFF_ROTATION = [
    ['gemini', 'coinbase'],
    ['strike', 'robinhood'],
    ['gemini_card', 'coinbase'],
    ['robinhood', 'gemini'],
]

def fetch_rss(url, max_items=5):
    """Fetch and parse an RSS feed. Returns list of {title, link, desc} dicts."""
    try:
        req = Request(url, headers={'User-Agent': 'Mozilla/5.0 FinanceFlowBot/1.0'})
        with urlopen(req, timeout=10) as resp:
            raw = resp.read()
        root = ET.fromstring(raw)
        ns   = {'atom': 'http://www.w3.org/2005/Atom'}
        items = root.findall('.//item') or root.findall('.//atom:entry', ns)
        results = []
        for item in items[:max_items]:
            title = item.findtext('title') or item.findtext('atom:title', namespaces=ns) or ''
            link  = item.findtext('link')  or item.findtext('atom:link',  namespaces=ns) or ''
            desc  = item.findtext('description') or item.findtext('summary') or item.findtext('atom:summary', namespaces=ns) or ''
            # Strip HTML tags from desc
            desc  = re.sub(r'<[^>]+>', '', html.unescape(desc)).strip()
            desc  = desc[:200] + '...' if len(desc) > 200 else desc
            title = html.unescape(title.strip())
            if title and link:
                results.append({'title': title, 'link': link, 'desc': desc})
        return results
    except Exception as e:
        print(f'  RSS fetch failed ({url}): {e}')
        return []

def get_news_stories():
    """Collect stories from multiple feeds with fallback."""
    stories = {'finance': [], 'crypto': []}
    for feed in RSS_FEEDS:
        items = fetch_rss(feed, max_items=4)
        stories['finance'].extend(items)
        if len(stories['finance']) >= 6:
            break
    for feed in CRYPTO_RSS_FEEDS:
        items = fetch_rss(feed, max_items=4)
        stories['crypto'].extend(items)
        if len(stories['crypto']) >= 4:
            break
    return stories

def build_news_article(stories):
    """Build a news roundup article dict from fetched RSS stories."""
    finance_stories = stories['finance'][:4]
    crypto_stories  = stories['crypto'][:3]
    all_stories = finance_stories + crypto_stories

    if not all_stories:
        return None  # no internet access — skip news this run

    slug_base = 'finance-news-roundup'
    slug      = f'{slug_base}-{TODAY}-{TS}'
    title     = pick([
        f'Finance News Roundup: What Happened This Week ({TODAY})',
        f'Markets & Money: Top Stories for {datetime.now().strftime("%B %d, %Y")}',
        f'Weekly Finance Digest: Latest News & Market Updates',
        f'This Week in Finance: Markets, Crypto & Money News',
    ])

    # Build sections HTML directly (bypasses template system)
    sections = []
    if finance_stories:
        body = '\n\n'.join(
            f'**{s["title"]}**\n{s["desc"]} <a href="{s["link"]}" target="_blank" rel="noopener noreferrer">Read more →</a>'
            for s in finance_stories
        )
        sections.append({'h': 'Top Finance & Market Stories', 'body': body})
    if crypto_stories:
        body = '\n\n'.join(
            f'**{s["title"]}**\n{s["desc"]} <a href="{s["link"]}" target="_blank" rel="noopener noreferrer">Read more →</a>'
            for s in crypto_stories
        )
        sections.append({'h': 'Crypto & Digital Assets', 'body': body})

    affiliates = random.choice(NEWS_AFF_ROTATION)

    return {
        'slug':      slug,
        'slug_base': slug_base,
        'title':     title,
        'tag':       'News',
        'emoji':     '📰',
        'bg':        '#f0f9ff',
        'desc':      f'The latest finance and crypto news for {datetime.now().strftime("%B %d, %Y")} — markets, investing updates, and what it means for your money.',
        'date':      TODAY,
        'sections':  sections,
        'affiliates': affiliates,
    }

# ── TOPIC TEMPLATES ─────────────────────────────────────────────────────────────
TOPICS = [
    {
        'slug': 'how-to-buy-bitcoin-beginners-guide',
        'titles': [
            'How to Buy Bitcoin for the First Time in 2026',
            "A Beginner's Complete Guide to Buying Bitcoin",
            'The Easiest Way to Buy Your First Bitcoin Right Now',
        ],
        'tag': 'Crypto', 'emoji': '₿', 'bg': '#fff7ed',
        'desc': 'Step-by-step guide to buying Bitcoin for the first time. Which exchange to use, how much to invest, and how to keep it safe.',
        'affiliates': ['strike', 'coinbase'],
        'sections': [
            {
                'h': 'Why Bitcoin Still Matters in 2026',
                'v': [
                    "Bitcoin has matured from a speculative curiosity into a legitimate store of value held by institutional investors, public companies, and even governments.\n\nThe good news: buying Bitcoin in 2026 is easier than ever. The whole process takes about 10 minutes if you use the right platform.",
                    "Love it or hate it, Bitcoin isn't going away. With a fixed supply of 21 million coins and growing institutional adoption, Bitcoin has earned its place in many investors' portfolios.\n\nThe barrier to entry has dropped dramatically. You can now buy as little as $1 of Bitcoin — no technical knowledge required.",
                ]
            },
            {
                'h': 'Step 1: Choose Your Exchange',
                'v': [
                    "Your first decision is which exchange to use. For beginners, we recommend either **Coinbase** (most beginner-friendly, 600+ coins) or **Strike** (Bitcoin-only, lowest fees).\n\nIf fees are your priority, Strike wins — your first $500 of Bitcoin is completely fee-free.",
                    "The exchange you choose matters for fees and ease of use. **Coinbase** is the most recognized name and requires minimal setup. **Strike** specializes in Bitcoin and offers near-zero fees.\n\nFor most beginners: start with Coinbase for simplicity, explore Strike as you get comfortable.",
                ]
            },
            {
                'h': 'Step 2: Verify Your Account',
                'v': [
                    "Exchanges require identity verification (KYC) — it's the same process as opening a bank account:\n\n1. Sign up with your email\n2. Provide your name, address, and date of birth\n3. Upload a photo of your government ID\n4. Wait for approval (usually instant)\n\nOnce verified, link your bank account and you're ready to buy.",
                    "Account verification is required by law. You'll need:\n• A valid government ID (driver's license or passport)\n• Your Social Security Number (last 4 digits on some platforms)\n• A bank account or debit card\n\nMost exchanges verify instantly. Start this step today.",
                ]
            },
            {
                'h': 'How Much Should You Buy?',
                'v': [
                    "The smartest approach for beginners is **dollar cost averaging (DCA)** — buying a fixed amount on a regular schedule regardless of price.\n\nExample: Buy $50 of Bitcoin every week. Over time, you buy more when prices are low and less when they're high.\n\nNever invest money you can't afford to lose. Start small and scale up as you learn.",
                    "Financial advisors generally suggest keeping crypto to 5–10% of your total investment portfolio.\n\nIf you're brand new, start with an amount you're comfortable losing — treat it as the price of financial education. Consistency beats timing every time.",
                ]
            },
        ],
    },

    {
        'slug': 'gemini-vs-coinbase-2026',
        'titles': [
            'Gemini vs Coinbase: Which Crypto Exchange Is Better in 2026?',
            'Coinbase vs Gemini: The Honest Comparison',
            'Gemini or Coinbase? Here\'s Which One to Choose',
        ],
        'tag': 'Crypto', 'emoji': '⚖️', 'bg': '#f0fdf4',
        'desc': 'Head-to-head comparison of Gemini and Coinbase — fees, security, coin selection, and sign-up bonuses — to help you choose the right exchange.',
        'affiliates': ['gemini', 'coinbase'],
        'sections': [
            {
                'h': 'The Quick Answer',
                'v': [
                    "Both are regulated, reputable US crypto exchanges. **Coinbase** wins on coin selection (600+) and beginner ease. **Gemini** wins on security credentials and a standout sign-up bonus: **$50 free crypto** when you trade $100.",
                    "Both exchanges are legitimate and safe. Coinbase is better for wider coin selection; Gemini is better for security and the most generous welcome bonus in crypto.",
                ]
            },
            {
                'h': 'Fees',
                'v': [
                    "Coinbase charges 1.49%–2.99% on standard purchases. Gemini charges similar spreads. Both offer lower-fee 'Pro' modes for experienced users.\n\nFor everyday buying, fees are comparable. Gemini's $50 welcome bonus effectively cancels months of fees.",
                    "Neither exchange is the cheapest on fees (that's Kraken or Binance US). But both prioritize regulatory compliance and security over minimum fees — a worthwhile trade-off for US users.",
                ]
            },
            {
                'h': 'Security',
                'v': [
                    "Gemini holds the edge. It's the only SOC 2 Type 2 certified crypto exchange and holds a NYDFS BitLicense — one of the strictest financial licenses in the US.\n\nCoinbase is publicly traded on NASDAQ (ticker: COIN) and holds licenses in all 50 states. Both are among the safest options available.",
                    "Gemini has more third-party security certifications and undergoes regular independent audits. Coinbase's public listing means it faces strict SEC reporting — a different but equally meaningful layer of accountability.",
                ]
            },
            {
                'h': 'Verdict',
                'v': [
                    "Open both. Seriously — both are free to join, and having two accounts gives you the best of each.\n\nStart with Gemini to claim the **$50 bonus** (trade $100, get $50 free). Then open Coinbase for its wider coin selection.",
                    "If you're only opening one: pick Gemini for the $50 referral bonus and top-tier security. Pick Coinbase if you want to explore smaller altcoins beyond the top 70.",
                ]
            },
        ],
    },

    {
        'slug': 'robinhood-review-2026',
        'titles': [
            'Robinhood Review 2026: Is It Still Worth Using?',
            'Robinhood in 2026: Honest Review After Years of Use',
            'Is Robinhood Good? Our 2026 Full Review',
        ],
        'tag': 'Investing', 'emoji': '🟢', 'bg': '#f0fdf4',
        'desc': 'An honest 2026 Robinhood review — commissions, the 3% IRA match, crypto trading, pros, cons, and who it\'s best for.',
        'affiliates': ['robinhood'],
        'sections': [
            {
                'h': 'What\'s Changed in 2026',
                'v': [
                    "Robinhood pioneered commission-free trading and forced the entire industry to follow. Today it's grown beyond stocks into crypto, options, and retirement accounts with a **3% IRA match**.\n\nThe platform has also cleaned up its reputation significantly since the 2021 GameStop controversy.",
                    "In 2026, Robinhood offers stocks, ETFs, options, crypto, and a surprisingly competitive 3% IRA match. The UI remains the simplest of any investing app — that's still its biggest advantage.",
                ]
            },
            {
                'h': 'What You Can Trade',
                'v': [
                    "Robinhood supports:\n• Stocks (US-listed)\n• ETFs\n• Options\n• Crypto (30+ coins including BTC, ETH, DOGE, SOL)\n• Fractional shares from $1\n\nNotably missing: mutual funds, international stocks, bonds. For those, consider Fidelity.",
                    "The asset selection covers most of what everyday investors need. Missing: fixed income, mutual funds, international markets. For a one-stop shop, Fidelity is more complete — but Robinhood's simplicity is genuinely valuable for beginners.",
                ]
            },
            {
                'h': 'The 3% IRA Match',
                'v': [
                    "Robinhood Gold subscribers get a **3% match on IRA contributions** — the best IRA match outside of an employer 401(k).\n\nOn the $7,000 annual IRA limit, that's $210 in free money. Robinhood Gold costs $60/year, so you're netting $150 profit just from the match — before counting any investment returns.",
                    "No other retail broker matches IRA contributions this generously. 3% on $7,000 = $210 free money annually. Robinhood Gold ($60/yr) pays for itself many times over through this feature alone.",
                ]
            },
            {
                'h': 'Pros and Cons',
                'v': [
                    "**Pros:**\n• $0 commissions on stocks, ETFs, and options\n• Cleanest, most beginner-friendly UI in the industry\n• Free gift stock for new sign-ups via referral\n• 3% IRA match with Robinhood Gold\n• Crypto trading built in\n\n**Cons:**\n• No mutual funds\n• Limited research tools\n• Customer support is email-only",
                    "**Best for:** Beginners who want simplicity. Anyone who wants a 3% IRA match. People who want stocks and crypto in one app.\n\n**Look elsewhere if:** You need advanced charting, screeners, mutual funds, or phone support. Fidelity or Schwab fit those needs better.",
                ]
            },
        ],
    },

    {
        'slug': 'dollar-cost-averaging-guide',
        'titles': [
            'Dollar Cost Averaging: The Strategy That Works While You Sleep',
            'What Is Dollar Cost Averaging? The Beginner\'s Guide',
            'How Dollar Cost Averaging Removes Emotion From Investing',
        ],
        'tag': 'Investing', 'emoji': '📅', 'bg': '#eff6ff',
        'desc': 'Dollar cost averaging explained — what it is, why it works, and how to automate it for stocks, ETFs, and crypto.',
        'affiliates': ['robinhood', 'coinbase'],
        'sections': [
            {
                'h': 'What Is Dollar Cost Averaging?',
                'v': [
                    "Dollar cost averaging (DCA) means investing a fixed dollar amount on a regular schedule — weekly, biweekly, or monthly — regardless of what the market is doing.\n\nWhen prices are low, your fixed amount buys more shares. When prices are high, it buys fewer. Over time, this smooths out your average purchase cost.",
                    "DCA is the strategy used by almost every 401(k) in the country — employees contribute a fixed percentage of each paycheck automatically, regardless of market conditions.\n\nThe principle: don't try to predict the market. Just buy consistently and let time do the work.",
                ]
            },
            {
                'h': 'Why It Works',
                'v': [
                    "DCA works for two reasons:\n\n**1. Removes emotion.** The biggest investing mistake is panic-selling during crashes. DCA forces you to keep buying even when everything looks scary — exactly when the best deals are available.\n\n**2. Removes the need to time the market.** Even professional fund managers can't reliably time the market. DCA sidesteps the problem entirely.",
                    "The biggest enemy of investment returns is the investor's own behavior — buying in excitement, selling in fear. DCA prevents this by automating the buying process.\n\nHistorically, someone who invested $200/month in the S&P 500 for 30 years would have significantly more money than someone who tried to time perfect entry points.",
                ]
            },
            {
                'h': 'DCA for Crypto',
                'v': [
                    "DCA is even more valuable for crypto, where volatility is extreme. Instead of trying to buy the dip, just buy $50 of Bitcoin every week.\n\nCoinbase and Gemini both support recurring crypto purchases. Set it once and let it run.\n\nHistorically, anyone who DCA'd into Bitcoin over any 4-year period has been profitable — even if they started at a local price peak.",
                    "Crypto DCA example: $100/week into Bitcoin starting January 2022 (near the peak). By 2025, that investor had a significant profit despite starting at what felt like the worst possible time.\n\nConsistency beats timing. Use Coinbase to set up automatic weekly crypto buys and stop agonizing over price.",
                ]
            },
        ],
    },

    {
        'slug': 'emergency-fund-guide',
        'titles': [
            'How Much Should You Have in an Emergency Fund? The Honest Answer',
            'Emergency Fund 101: Build One Even on a Tight Budget',
            'Building an Emergency Fund: How Much, Where, and How Fast',
        ],
        'tag': 'Saving', 'emoji': '🛡️', 'bg': '#f0fdf4',
        'desc': 'How much to save in your emergency fund, where to keep it, and the fastest way to build one — even on a tight budget.',
        'affiliates': ['robinhood'],
        'sections': [
            {
                'h': 'How Much Do You Actually Need?',
                'v': [
                    "The classic advice is 3–6 months of expenses. But the right amount depends on your situation:\n\n• **Stable job, dual income:** 3 months is enough\n• **Single income or variable income:** 6 months minimum\n• **Self-employed or freelance:** 9–12 months recommended\n\nThe goal: be able to pay your bills for that many months if all income stopped tomorrow.",
                    "Define 'expenses' correctly: rent/mortgage, food, utilities, insurance, and minimum debt payments. Not your lifestyle spending.\n\nMost people overestimate their required emergency fund. Start with 1 month — it covers most real emergencies — then build toward 3.",
                ]
            },
            {
                'h': 'Where to Keep It',
                'v': [
                    "Your emergency fund should be:\n1. **Liquid** — accessible in 24 hours\n2. **Safe** — FDIC insured\n3. **Earning interest** — not sitting in a 0.01% APY checking account\n\nThe best home is a **high-yield savings account (HYSA)**. Top HYSAs pay 4–5% APY — on a $10,000 fund, that's $400–$500/year in free interest.",
                    "Never keep your emergency fund in stocks or crypto. The whole point is that it's there when you need it — markets can be down 40% exactly when you lose your job.\n\nKeep it in a HYSA: FDIC insured, earns 4–5% APY (vs 0.01% at big banks), and you can access it in 24 hours.",
                ]
            },
            {
                'h': 'How to Build It Fast',
                'v': [
                    "Break it into milestones:\n\n**Month 1–2:** Save $500 — covers most minor emergencies\n**Month 3–4:** Reach $1,000 — covers car repairs, medical bills\n**Month 5+:** Continue until you hit 3 months of expenses\n\nTreat your emergency fund contribution like a bill. Set up an automatic transfer on payday before you can spend the money.",
                    "Practical ways to build it faster:\n• **Automate it:** Set up a weekly transfer to your HYSA — whatever you can afford\n• **Windfall rule:** Put 50% of any unexpected money (tax refund, bonus) directly into the fund\n• **Cut one expense:** Cancel one subscription and redirect that exact amount to savings",
                ]
            },
        ],
    },

    {
        'slug': 'high-yield-savings-account-guide',
        'titles': [
            'High-Yield Savings Accounts in 2026: Everything You Need to Know',
            'Why Your Savings Account Is Costing You Thousands',
            'Earn 10x More Interest: High-Yield Savings Accounts Explained',
        ],
        'tag': 'Saving', 'emoji': '🏦', 'bg': '#f0fdf4',
        'desc': 'How high-yield savings accounts work, how much more you\'ll earn vs a traditional bank, and how to open one in 10 minutes.',
        'affiliates': ['gemini'],
        'sections': [
            {
                'h': 'The Problem: Your Bank Is Ripping You Off',
                'v': [
                    "The national average savings APY at big banks (Chase, Bank of America, Wells Fargo) is 0.01%. That means on $10,000, you earn $1 per year.\n\nMeanwhile, inflation runs at 2–4% annually. You're effectively losing purchasing power every month your money sits there.",
                    "Here's a number that should make you angry: 0.01% APY. On $10,000, that's $1/year.\n\nHigh-yield savings accounts pay 4–5% APY on the same money — $400–$500/year. Same FDIC insurance. Same access. You just need to log into a different app.",
                ]
            },
            {
                'h': 'What Makes It "High-Yield"?',
                'v': [
                    "High-yield savings accounts are offered by online banks — no physical branches, lower overhead. They pass those savings to customers as higher interest.\n\nHYSAs are:\n• FDIC insured up to $250,000\n• Liquid — access your money in 1–2 business days\n• Simple — it's just a savings account with a better rate",
                    "Online banks can offer 4–5% APY because they don't maintain thousands of physical branches. That cost savings goes straight into your interest rate.\n\nHYSAs are not investments or exotic products. They're regular FDIC-insured savings accounts. The only difference is the number after the % sign.",
                ]
            },
            {
                'h': 'The Math',
                'v': [
                    "Let's say you have $15,000 in savings:\n\n• Big bank at 0.01% APY: **$1.50/year**\n• High-yield savings at 4.5% APY: **$675/year**\n\nThat's $673.50 in free money for switching accounts. Over 5 years with compound interest, the difference grows to over $3,500.",
                    "Example with $25,000:\n• Chase savings at 0.01% APY: $2.50/year\n• HYSA at 4.5% APY: $1,125/year\n\nEvery day you wait costs you about $3. The account opening takes 10 minutes. There's no good reason to keep your savings at a big bank.",
                ]
            },
        ],
    },

    {
        'slug': 'how-to-invest-50-dollars-month',
        'titles': [
            'How to Start Investing With Just $50 a Month',
            '$50 a Month: What It Grows to Over 10, 20, and 30 Years',
            'You Don\'t Need a Lot of Money to Start Investing — Here\'s the Proof',
        ],
        'tag': 'Investing', 'emoji': '📈', 'bg': '#eff6ff',
        'desc': 'How $50/month grows through compound interest, which accounts to use, and the exact steps to start investing today.',
        'affiliates': ['robinhood', 'coinbase'],
        'sections': [
            {
                'h': 'The Math on $50 a Month',
                'v': [
                    "**$50/month at 7% annual return:**\n• After 10 years: **$8,654**\n• After 20 years: **$26,126**\n• After 30 years: **$60,905**\n\nYou contributed $18,000. Compound interest did the rest — $42,905 that you never earned yourself.",
                    "The biggest investing myth: you need a lot of money to get started.\n\n$50/month invested consistently for 30 years at 7% = **$60,905**. You only put in $18,000. That's compound interest at work — almost 75% of your final balance is money you never worked for.",
                ]
            },
            {
                'h': 'Where to Put Your $50',
                'v': [
                    "The simplest path:\n\n1. **Open a Roth IRA** (tax-free growth forever)\n2. **Buy VOO or VTI** (S&P 500 / total market index ETF)\n3. **Set up automatic monthly purchases**\n4. **Don't touch it**\n\nRobinhood offers Roth IRAs with $0 minimums and fractional shares — start with $50.",
                    "For most beginners: Roth IRA → index ETFs → automate.\n\n• **Roth IRA:** Tax-free growth. Every dollar of gains comes out tax-free in retirement.\n• **VOO or VTI:** Instant diversification across 500–3,500 companies. Expense ratio under 0.05%.\n• **Automate:** Set recurring purchases on payday.\n\nThis beats most professional money managers over 30 years.",
                ]
            },
            {
                'h': 'The One Thing That Matters',
                'v': [
                    "Time in the market beats timing the market — always.\n\nEvery month you wait to start is compounding you can never recover. The best time was 10 years ago. The second best time is today.\n\nOpen an account, set up a $50 recurring investment, and stop thinking about it.",
                    "The single most important investing decision you'll make is to start.\n\nNot which stocks to pick. Not when to buy. Just whether you start at all.\n\nOpen Robinhood today, set up a recurring $50 into VOO, and you've already beaten the 90% of people who say they'll invest 'when things calm down' — and never do.",
                ]
            },
        ],
    },

    {
        'slug': 'gemini-credit-card-review-2026',
        'titles': [
            'Gemini Credit Card Review 2026: Is 4% Crypto Cashback Worth It?',
            'The Gemini Credit Card: Everything You Need to Know',
            'Earn Crypto on Every Purchase: Gemini Credit Card Full Review',
        ],
        'tag': 'Crypto', 'emoji': '💎', 'bg': '#fdf4ff',
        'desc': 'Full review of the Gemini Credit Card — 4% dining rewards, how real-time crypto cashback works, who it\'s best for, and whether it\'s worth applying.',
        'affiliates': ['gemini_card', 'gemini'],
        'sections': [
            {
                'h': 'What Is the Gemini Credit Card?',
                'v': [
                    "The Gemini Credit Card earns cryptocurrency on every purchase instead of points or cash back. No annual fee, no foreign transaction fees, and rewards deposit instantly into your Gemini wallet.\n\nRewards rates:\n• **Dining:** 4% back in crypto\n• **Groceries:** 3% back in crypto\n• **Everything else:** 1% back in crypto",
                    "A Mastercard that converts everyday spending into cryptocurrency. You choose which coin receives your rewards — Bitcoin, Ethereum, or any of 60+ assets.\n\nKey facts: No annual fee. No foreign transaction fees. Rewards hit your account in seconds, not at month-end.",
                ]
            },
            {
                'h': 'How the Rewards Actually Work',
                'v': [
                    "Every time you swipe, your cashback converts to crypto at the current market rate and deposits into your Gemini account within seconds. No waiting, no minimums, no manual redemption.\n\nThis means your dining cashback starts earning price appreciation immediately. If you earn 4% back in Bitcoin and Bitcoin goes up, your rewards are worth more.",
                    "Swipe card → cashback calculated → crypto purchased at market rate → deposited to Gemini wallet. The whole process is instant.\n\nYou pick your reward coin in the app settings (changeable anytime). You're accumulating crypto with every purchase, whether prices are up or down on that day.",
                ]
            },
            {
                'h': 'Is 4% Crypto Cashback Good?',
                'v': [
                    "For dining specifically: yes, 4% is excellent. Most premium cash-back cards top out at 3% on dining — and charge annual fees of $95–$550.\n\nGemini's 4% dining reward with a $0 annual fee is genuinely competitive against any rewards card on the market.",
                    "To put 4% in context: the Capital One Savor offers 4% dining cashback — for a $95 annual fee. Gemini matches that rate with zero annual fee, with the caveat that rewards are in crypto.\n\nIf you're comfortable holding some crypto, this is one of the best dining reward rates available anywhere.",
                ]
            },
        ],
    },

    {
        'slug': 'passive-income-ideas-2026',
        'titles': [
            '8 Realistic Passive Income Ideas That Actually Work in 2026',
            'How to Build Passive Income From Scratch in 2026',
            'Passive Income in 2026: What\'s Working Right Now',
        ],
        'tag': 'Investing', 'emoji': '💸', 'bg': '#fefce8',
        'desc': 'Realistic passive income ideas for 2026 — dividend investing, crypto staking, affiliate income, and more. How much each earns and how to start.',
        'affiliates': ['robinhood', 'gemini'],
        'sections': [
            {
                'h': 'Dividend Investing',
                'v': [
                    "Buy shares of dividend-paying stocks or ETFs and receive quarterly payments. A 4% dividend yield on $10,000 = $400/year — $33/month — for doing nothing after the initial purchase.\n\nBest dividend ETFs: **SCHD** (Schwab US Dividend Equity), **VYM** (Vanguard High Dividend Yield), **JEPI** (JPMorgan Equity Premium Income, ~7% yield).\n\nUse Robinhood or Fidelity to set up automatic reinvestment (DRIP) and watch compounding accelerate.",
                    "Dividend investing is the most proven passive income method. You buy profitable companies. They share profits quarterly. You reinvest those dividends to buy more shares.\n\nREITs (Real Estate Investment Trusts) pay dividends too — often 5–8% yields — letting you earn real estate income without owning property.",
                ]
            },
            {
                'h': 'Crypto Staking',
                'v': [
                    "Staking means locking up cryptocurrency to help validate blockchain transactions. In return, you earn rewards — essentially interest on your crypto.\n\nCurrent approximate staking yields:\n• Ethereum (ETH): ~3–4% annually\n• Solana (SOL): ~6–7% annually\n\nGemini offers staking on multiple assets directly from the platform — no technical setup required.",
                    "If you're holding crypto long-term, staking is free money. You're not selling — you're putting existing holdings to work.\n\nGemini's staking feature lets you earn directly from your account. Rates vary by asset and market conditions, but passive crypto yield beats leaving coins idle.",
                ]
            },
            {
                'h': 'Affiliate Marketing',
                'v': [
                    "Refer people to products and earn a commission when they sign up — this is literally how this site earns money.\n\nFinancial affiliate programs pay well:\n• Crypto exchanges: $10–$50 per new user\n• Robinhood: you both get a free stock\n• Credit cards: $50–$200 per approval\n\nA single well-placed affiliate link in a blog post can earn for years with zero ongoing effort.",
                    "Affiliate income is passive once set up. Write a review once. Share a link once. Earn commissions for months as people find the content organically.\n\nBest niches by commission: finance (highest per conversion), software/SaaS (recurring monthly commissions), health (massive audience).",
                ]
            },
        ],
    },

    {
        'slug': 'debt-avalanche-vs-snowball',
        'titles': [
            'Debt Avalanche vs Snowball: Which Method Saves More Money?',
            'How to Pay Off Debt Fast: Avalanche vs Snowball Explained',
            'The Best Way to Pay Off Multiple Debts in 2026',
        ],
        'tag': 'Debt', 'emoji': '💳', 'bg': '#fefce8',
        'desc': 'A clear comparison of the debt avalanche and snowball methods — which saves more money, which keeps you motivated, and exactly how to choose.',
        'affiliates': ['robinhood'],
        'sections': [
            {
                'h': 'The Two Methods',
                'v': [
                    "**Debt Avalanche:** Pay minimums on all debts, throw extra money at the highest-interest debt first. Mathematically optimal — saves the most in interest.\n\n**Debt Snowball:** Pay minimums on all debts, throw extra money at the smallest balance first. Psychologically optimal — quick wins keep you motivated.",
                    "Both methods are identical except for which debt gets your extra payment each month.\n\n• **Avalanche** = highest interest rate first\n• **Snowball** = smallest balance first\n\nBoth dramatically accelerate payoff compared to minimum payments only.",
                ]
            },
            {
                'h': 'Which Saves More Money?',
                'v': [
                    "The avalanche always saves more interest — sometimes significantly.\n\nExample: $20,000 across three debts (15% credit card, 8% personal loan, 4% car loan), $300 extra/month:\n\n• **Avalanche:** Debt-free in 48 months, $4,200 in interest\n• **Snowball:** Debt-free in 51 months, $5,100 in interest\n\n$900 more in your pocket with avalanche.",
                    "Mathematically, the avalanche wins every time. The gap is largest when you have high-interest debt (credit cards), a long timeline, and large rate differences between debts.\n\nFor most people with credit card debt, the avalanche saves $1,000–$3,000+ in interest.",
                ]
            },
            {
                'h': 'Which Method Works for YOU?',
                'v': [
                    "The best debt payoff method is the one you actually stick with.\n\nResearch shows most people fail at debt payoff not because of a bad strategy but because they lose motivation. The snowball's quick wins combat this.\n\nIf you're disciplined: use the avalanche. If you need emotional momentum: use the snowball. Either beats minimum payments.",
                    "Dave Ramsey advocates the snowball because he's seen thousands fail with mathematically optimal plans they couldn't sustain.\n\nBut if you can stay motivated with the avalanche, the extra savings are real money. Use our free debt payoff calculator to see the exact numbers for your situation.",
                ]
            },
        ],
    },

    {
        'slug': 'bitcoin-lightning-network-explained',
        'titles': [
            'What Is the Bitcoin Lightning Network? A Simple Explanation',
            'Lightning Network Explained: Why Bitcoin Payments Are Now Instant',
            'Strike and Lightning Network: How Bitcoin Became Usable Every Day',
        ],
        'tag': 'Crypto', 'emoji': '⚡', 'bg': '#fefce8',
        'desc': 'The Bitcoin Lightning Network explained simply — what it is, how it makes Bitcoin instant and free, and why Strike is built on it.',
        'affiliates': ['strike', 'coinbase'],
        'sections': [
            {
                'h': 'Bitcoin\'s Speed Problem',
                'v': [
                    "Bitcoin is great as a store of value but has a limitation: the main blockchain processes only ~7 transactions per second. Visa handles 24,000 per second.\n\nBitcoin transactions can take 10+ minutes and cost $5–$50 in fees during busy periods — terrible for everyday payments. The Lightning Network solves this.",
                    "Bitcoin's blockchain is intentionally slow and secure. Every transaction is permanently recorded on a distributed ledger verified by thousands of nodes worldwide. This security comes with a cost: speed and fees.\n\nFor buying coffee or sending $5, waiting 10 minutes and paying $20 doesn't work. Lightning is Bitcoin's answer.",
                ]
            },
            {
                'h': 'How Lightning Works',
                'v': [
                    "Lightning creates 'payment channels' between users — like running a tab at a bar, settling multiple transactions at once.\n\nInside a Lightning channel: transactions are **instant and nearly free**. Only opening and closing a channel touches the main blockchain.\n\nResult: thousands of transactions per second, fees under $0.01, settlement in milliseconds.",
                    "Lightning Network is a 'second layer' on top of Bitcoin:\n\n1. Two parties open a payment channel (one blockchain transaction)\n2. Exchange unlimited instant payments through that channel\n3. Close the channel when done (one more blockchain transaction)\n\nNet result: instant Bitcoin payments at essentially zero cost.",
                ]
            },
            {
                'h': 'Strike: Lightning Made Simple',
                'v': [
                    "Strike is one of the most popular Lightning Network apps in the US. It lets you buy Bitcoin instantly with near-zero fees, and send Bitcoin to anyone for fractions of a cent.\n\nStrike's standout offer for new users: your **first $500 of Bitcoin is completely fee-free**. No catch.",
                    "Strike abstracts away all Lightning Network complexity into a clean, simple app. You don't need to understand payment channels — it just works.\n\nFor buying Bitcoin, Strike is one of the lowest-fee options available. The first $500 is completely free, and fees after that remain very competitive.",
                ]
            },
        ],
    },

    {
        'slug': 'roth-ira-beginners-guide',
        'titles': [
            'Roth IRA Explained: The Best Retirement Account Most People Aren\'t Using',
            'How to Open a Roth IRA in 2026 (Step-by-Step)',
            'Why You Should Open a Roth IRA Before Any Other Investment Account',
        ],
        'tag': 'Investing', 'emoji': '🏛️', 'bg': '#eff6ff',
        'desc': 'A complete beginner\'s guide to Roth IRAs — what they are, why they\'re powerful, 2026 contribution limits, and how to open one in minutes.',
        'affiliates': ['robinhood'],
        'sections': [
            {
                'h': 'What Is a Roth IRA?',
                'v': [
                    "A Roth IRA is a retirement account where you contribute after-tax dollars — and then all growth and withdrawals are **completely tax-free**.\n\nExample: Invest $6,000 at 25. By 65, it grows to $90,000 at 7% return. You pay taxes on the $6,000. The $84,000 in gains? Zero taxes. Forever.",
                    "IRA = Individual Retirement Account. The 'Roth' version has a unique tax structure: pay taxes now, never pay taxes again on the growth.\n\nFor most people under 40, the Roth IRA is the single best investment account available — better than a regular brokerage account because of tax-free compounding.",
                ]
            },
            {
                'h': '2026 Contribution Limits',
                'v': [
                    "In 2026, you can contribute up to **$7,000/year** to a Roth IRA ($8,000 if you're 50+).\n\nIncome limits: full contribution allowed under $146,000 (single) or $230,000 (married filing jointly).\n\n$7,000/year = ~$583/month = ~$134/week.",
                    "2026 Roth IRA limits:\n• Under 50: **$7,000/year**\n• 50 and older: **$8,000/year** (catch-up contribution)\n\nPhase-out starts at $146,000 MAGI for single filers. You must have earned income at least equal to your contribution.",
                ]
            },
            {
                'h': 'How to Open One',
                'v': [
                    "Opening a Roth IRA takes 10 minutes:\n\n1. Choose a brokerage (Fidelity, Vanguard, or Robinhood)\n2. Click 'Open a Roth IRA'\n3. Fill in your personal info\n4. Fund via bank transfer\n5. Invest in a target-date fund or index ETF\n\nRobinhood offers a 3% IRA contribution match for Gold members — a compelling offer.",
                    "The barrier is lower than most people think:\n• No minimum balance at most brokers\n• 10–15 minutes to set up\n• Start investing the same day\n\nThe most common mistake: waiting until you have 'enough.' Start with $50. Time is the main ingredient — and every year you wait costs you thousands in compounding.",
                ]
            },
        ],
    },

    {
        'slug': 'index-funds-explained',
        'titles': [
            'Index Funds: The Investment Even Warren Buffett Recommends',
            'What Are Index Funds and Why Do They Beat Stock Pickers?',
            'Index Funds for Beginners: A Complete 2026 Guide',
        ],
        'tag': 'Investing', 'emoji': '📊', 'bg': '#eff6ff',
        'desc': 'Index funds explained from scratch — what they are, why they outperform most active investors, and how to buy your first one today.',
        'affiliates': ['robinhood'],
        'sections': [
            {
                'h': 'What Is an Index Fund?',
                'v': [
                    "An index fund holds stocks that mirror a market index — most commonly the S&P 500 (500 largest US companies).\n\nInstead of picking individual stocks, you buy tiny pieces of all 500 companies at once. When the market goes up, your fund goes up.\n\nThe S&P 500 has returned an average of ~10.5% annually since 1957.",
                    "An index fund is the simplest investment vehicle that works. You're buying the whole market, not betting on individual companies.\n\nMost popular example: **VOO** (Vanguard S&P 500 ETF). It holds the same stocks as the S&P 500 and charges just 0.03% per year — $3 on a $10,000 investment.",
                ]
            },
            {
                'h': 'Why They Beat Most Active Investors',
                'v': [
                    "Over any 15-year period, more than **90% of actively managed mutual funds underperform the S&P 500 index**.\n\nProfessional fund managers — with MBAs, Bloomberg terminals, and decades of experience — can't beat a simple index fund 9 out of 10 times. Yet they charge 1–2% in annual fees.",
                    "The S&P 500 SPIVA report: 91% of large-cap active funds underperformed the S&P 500 over 20 years.\n\nReasons: fees eat returns, markets are highly efficient, and past performance doesn't predict future results. Index funds don't try to beat the market — they are the market.",
                ]
            },
            {
                'h': 'The Best Index Funds to Start With',
                'v': [
                    "For most beginners, one of these three is all you need:\n\n• **VOO** — Vanguard S&P 500 ETF, 0.03% expense ratio\n• **VTI** — Vanguard Total Stock Market ETF, 0.03%\n• **VT** — Vanguard Total World Stock ETF, 0.07% (global)\n\nAll available commission-free on Robinhood and Fidelity.",
                    "Start simple:\n• **US exposure:** VOO or VTI\n• **Global exposure:** VT, or 60% VTI + 40% VXUS\n• **One fund forever:** VT\n\nDon't overthink it. Pick one, automate monthly purchases, and check prices less often. That's the entire strategy.",
                ]
            },
        ],
    },

    {
        'slug': 'best-crypto-exchanges-2026',
        'titles': [
            'Best Crypto Exchanges in 2026: Ranked by Fees, Security & Bonuses',
            'Top Crypto Exchanges for US Users in 2026',
            'Which Crypto Exchange Should You Use in 2026?',
        ],
        'tag': 'Crypto', 'emoji': '🏆', 'bg': '#fdf4ff',
        'desc': 'The top crypto exchanges for US users in 2026 — ranked by fees, security, coin selection, and sign-up bonuses.',
        'affiliates': ['gemini', 'coinbase', 'strike'],
        'sections': [
            {
                'h': 'What to Look For',
                'v': [
                    "Not all exchanges are equal. Prioritize:\n\n1. **Regulation** — licensed in your state?\n2. **Security** — SOC 2 certification, insurance, track record?\n3. **Fees** — total all-in cost per purchase\n4. **Coin selection** — does it list the assets you want?\n5. **Sign-up bonus** — some exchanges pay you just to join",
                    "The FTX collapse of 2022 proved: not all exchanges can be trusted. Stick to regulated, audited US exchanges with verifiable reserves.\n\nKey criteria: US-regulated, FDIC coverage on USD, transparent fees, no history of misusing customer funds.",
                ]
            },
            {
                'h': 'Gemini — Best Security + Best Bonus',
                'v': [
                    "Gemini is the most regulated US crypto exchange: NYDFS BitLicense, SOC 2 Type 2 certified, regular third-party audits.\n\n**The bonus:** Trade $100 → receive $50 in free crypto. A 50% instant return on your first trade — no other major exchange matches this.\n\nBest for: security-conscious users and anyone who wants the best sign-up bonus.",
                    "Founded by the Winklevoss twins, Gemini operates under the strictest US regulatory framework and submits to independent security audits.\n\nThe referral bonus is uniquely generous: $50 free crypto for trading $100. One of the highest ROI sign-up offers in personal finance.",
                ]
            },
            {
                'h': 'Strike — Best for Bitcoin',
                'v': [
                    "For Bitcoin specifically, Strike offers the best fees via the Lightning Network. Your first $500 of Bitcoin is completely fee-free — no other major platform matches this.\n\nStrike doesn't try to be everything. It's Bitcoin-focused with the simplest interface available.\n\nBest for: Bitcoin-first investors who care most about fees.",
                    "Strike's Bitcoin focus via Lightning Network results in genuinely better fees than any general-purpose exchange.\n\nThe $0 fees on the first $500 is compelling for new buyers — your first Bitcoin purchase is effectively 100% fee-free.",
                ]
            },
        ],
    },

    {
        'slug': 'compound-interest-explained',
        'titles': [
            'How Compound Interest Works: Why Einstein Called It the 8th Wonder',
            'Compound Interest Explained: The Math That Makes or Breaks Your Wealth',
            'The Power of Compound Interest: Why Starting Early Changes Everything',
        ],
        'tag': 'Investing', 'emoji': '🔢', 'bg': '#eff6ff',
        'desc': 'Compound interest explained simply with real examples — how it builds wealth and why starting early is the most important financial decision you can make.',
        'affiliates': ['robinhood'],
        'sections': [
            {
                'h': 'Simple vs Compound Interest',
                'v': [
                    "Simple interest earns returns on your original investment only. Compound interest earns returns on your investment **plus all previous returns**.\n\n• $10,000 at 7% simple for 30 years → **$31,000**\n• $10,000 at 7% compound for 30 years → **$76,122**\n\nSame money, same rate, same time. The difference is whether returns earn returns.",
                    "Compound interest means your money earns money on its money — and that money earns money on that money.\n\nThe formula: **A = P(1 + r)^t**\n\nAt 7%: your money grows 3.9× in 20 years, 7.6× in 30 years, 14.9× in 40 years. Time is the main variable.",
                ]
            },
            {
                'h': 'The Rule of 72',
                'v': [
                    "Quick mental math: divide 72 by your interest rate to find years to double your money.\n\n• At 6% → doubles every 12 years\n• At 7% → doubles every ~10 years\n• At 10% → doubles every 7.2 years\n\nS&P 500 historical return (~10%): your money doubles roughly every 7 years.",
                    "Doubling times by rate:\n\n| Rate | Years to Double |\n|------|----------------|\n| 4% | 18 years |\n| 6% | 12 years |\n| 8% | 9 years |\n| 10% | 7.2 years |\n\nThis is why starting early matters more than starting with a large amount.",
                ]
            },
            {
                'h': 'Why Starting Early Beats Earning More',
                'v': [
                    "**Alex** invests $5,000/year from age 25–35 (10 years), then stops. Total invested: $50,000.\n**Jordan** invests $5,000/year from age 35–65 (30 years). Total invested: $150,000.\n\nAt 65 (7% return):\n• Alex: **$602,000**\n• Jordan: **$472,000**\n\nAlex invested a third as much money and still won by $130,000. Starting a decade earlier overwhelms 30 extra years of contributions.",
                    "Time is worth more than money in investing. Starting at 25 vs 35 isn't a 10-year head start — it's potentially hundreds of thousands of dollars at retirement.\n\nEvery year you delay is compounding you can never recover. The best time to start is right now.",
                ]
            },
        ],
    },

    {
        'slug': 'how-to-save-money-tight-budget',
        'titles': [
            'How to Save Money on a Tight Budget: What Actually Works in 2026',
            'Saving Money When You\'re Broke: Realistic Tips',
            'How to Save $500 a Month Even When You Think You Can\'t',
        ],
        'tag': 'Budgeting', 'emoji': '✂️', 'bg': '#f0fdf4',
        'desc': 'Practical, realistic tips for saving money on a tight budget in 2026 — no extreme couponing or sacrifice required.',
        'affiliates': ['robinhood'],
        'sections': [
            {
                'h': 'The Mindset Shift',
                'v': [
                    "Most people think of saving as what's left after spending. The shift that changes everything: **savings is a bill you pay first**.\n\nSet up an automatic transfer to savings on payday — before you can spend it. Even $25. The amount matters less than the habit.\n\nUnused gym memberships cost Americans $1.8 billion annually. Most people have more room to save than they think.",
                    "Pay yourself first: set up a recurring transfer to a high-yield savings account on every payday.\n\nStart with whatever doesn't feel uncomfortable — $50, $100, $200. You'll naturally adjust your spending to match what's left. That's the entire system.",
                ]
            },
            {
                'h': 'The Biggest Wins',
                'v': [
                    "Focus on the big three: housing, transportation, and food. These represent 60–70% of most budgets. A 10% reduction in each saves more than cutting every other expense combined.\n\n• **Housing:** Add a roommate ($400–$800/month saved)\n• **Transportation:** Refinance your auto loan if rates have dropped\n• **Food:** Meal prep twice a week — cuts dining out by ~50%",
                    "Finance advice obsesses over small cuts while ignoring the big levers:\n\n• Negotiate rent at renewal: save $100–$300/month\n• Refinance loans at better rates: save $200–$500/month\n• Switch to a cheaper cell plan: save $30–$80/month\n• Cut 2 streaming services: save $20–$40/month\n\nThese five moves can free up $500+/month without feeling deprived.",
                ]
            },
            {
                'h': 'Where to Put What You Save',
                'v': [
                    "The savings order that maximizes your money:\n\n1. **Emergency fund** (3 months of expenses in a HYSA at 4–5% APY)\n2. **401(k) match** (always get the full employer match — it's free money)\n3. **Roth IRA** (tax-free growth, up to $7,000/year in 2026)\n4. **HYSA** for goals under 5 years\n5. **Taxable brokerage** for long-term beyond IRA limits",
                    "Where your money sits matters almost as much as how much you save:\n\n• Move savings to a high-yield account (4–5% APY vs 0.01% at big banks)\n• Use Roth IRA first for retirement (tax-free growth)\n• Minimize taxes through tax-advantaged accounts before taxable investing\n\nTaxes are the biggest drag on long-term wealth. Using Roth IRAs and 401(k)s is the highest-leverage financial move most people can make.",
                ]
            },
        ],
    },
]


# ── TRACKING ───────────────────────────────────────────────────────────────────
def load_tracking():
    if TRACKING_FILE.exists():
        with open(TRACKING_FILE, 'r') as f:
            return json.load(f)
    return []

def save_tracking(data):
    with open(TRACKING_FILE, 'w') as f:
        json.dump(data, f, indent=2)


# ── TOPIC SELECTION ────────────────────────────────────────────────────────────
def pick_topics(tracking, count):
    recent_slugs = {a['slug_base'] for a in tracking[-30:]}
    available = [t for t in TOPICS if t['slug'] not in recent_slugs]
    if len(available) < count:
        available = TOPICS  # reset if we've used them all
    return random.sample(available, min(count, len(available)))

def recent_news_count(tracking):
    """How many news roundups published today already."""
    return sum(1 for a in tracking if a.get('slug_base') == 'finance-news-roundup' and a.get('date') == TODAY)


# ── ARTICLE GENERATION ─────────────────────────────────────────────────────────
def generate_article(topic):
    title   = pick(topic['titles'])
    slug    = f"{topic['slug']}-{TODAY}-{TS}"
    sections = [{'h': s['h'], 'body': pick(s['v'])} for s in topic['sections']]
    affiliates = topic['affiliates']
    return {
        'slug':     slug,
        'slug_base': topic['slug'],
        'title':    title,
        'tag':      topic['tag'],
        'emoji':    topic['emoji'],
        'bg':       topic['bg'],
        'desc':     topic['desc'],
        'date':     TODAY,
        'sections': sections,
        'affiliates': affiliates,
    }


# ── HTML BUILDER ───────────────────────────────────────────────────────────────
def build_article_html(article):
    slug      = article['slug']
    title     = article['title']
    tag       = article['tag']
    emoji     = article['emoji']
    bg        = article['bg']
    date_str  = article['date']
    desc      = article['desc']
    sections  = article['sections']
    aff_keys  = article['affiliates'][:2]

    sections_html = ''
    for s in sections:
        body = md(s['body'])
        sections_html += f'''
        <h2>{s["h"]}</h2>
        <p>{body}</p>
'''

    cta_html = ''
    for key in aff_keys:
        a = AFF[key]
        cta_html += f'''
        <div class="aff-cta">
          <div class="aff-cta-body">
            <strong>{a["name"]}</strong>
            <p>{a["bonus"]}</p>
          </div>
          <a href="{a["url"]}" class="btn-affiliate" target="_blank" rel="noopener noreferrer">{a["cta"]}</a>
        </div>
'''

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta name="description" content="{desc}" />
  <title>{title} — FinanceFlow</title>
  <link rel="stylesheet" href="../css/style.css" />
  <style>
    .article-hero {{ background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%); padding: 3rem 1.5rem 2rem; text-align: center; }}
    .article-hero h1 {{ font-size: clamp(1.6rem, 3.5vw, 2.4rem); font-weight: 900; color: var(--gray-900); max-width: 760px; margin: 0 auto 0.5rem; line-height: 1.2; }}
    .article-hero .meta {{ display: flex; justify-content: center; gap: 1rem; flex-wrap: wrap; margin-top: 0.75rem; font-size: 0.85rem; color: var(--gray-600); }}
    .article-wrap {{ max-width: 760px; margin: 0 auto; padding: 2rem 1.5rem 4rem; }}
    .article-wrap h2 {{ font-size: 1.25rem; font-weight: 800; color: var(--gray-900); margin: 2rem 0 0.6rem; }}
    .article-wrap p {{ color: var(--gray-600); line-height: 1.8; margin-bottom: 1rem; }}
    .aff-cta {{ display: flex; align-items: center; justify-content: space-between; gap: 1rem; background: var(--green-light); border: 1px solid #86efac; border-radius: 10px; padding: 1.25rem 1.5rem; margin: 2rem 0; flex-wrap: wrap; }}
    .aff-cta strong {{ color: var(--gray-900); display: block; margin-bottom: 0.2rem; }}
    .aff-cta p {{ margin: 0; font-size: 0.88rem; color: var(--gray-600); }}
    .aff-cta .btn-affiliate {{ flex-shrink: 0; white-space: nowrap; }}
    .back-link {{ display: inline-flex; align-items: center; gap: 0.4rem; color: var(--green); font-weight: 600; font-size: 0.9rem; margin-bottom: 1.5rem; }}
    table {{ width: 100%; border-collapse: collapse; margin: 1rem 0 1.5rem; font-size: 0.9rem; }}
    th {{ background: var(--green-light); color: var(--gray-900); padding: 0.6rem 0.8rem; text-align: left; }}
    td {{ padding: 0.6rem 0.8rem; border-bottom: 1px solid var(--gray-200); color: var(--gray-600); }}
  </style>
</head>
<body>

<nav>
  <a class="nav-logo" href="../index.html">Finance<span>Flow</span></a>
  <ul class="nav-links" id="navLinks">
    <li><a href="../index.html">Home</a></li>
    <li><a href="../calculator.html">Calculators</a></li>
    <li><a href="../recommendations.html">Top Picks</a></li>
    <li><a href="../blog.html">Guides</a></li>
    <li><a href="../recommendations.html" class="nav-cta">Top Picks →</a></li>
  </ul>
  <button class="nav-toggle" id="navToggle" aria-label="Toggle menu">
    <span></span><span></span><span></span>
  </button>
</nav>

<div class="article-hero">
  <div style="font-size:3rem;margin-bottom:0.5rem">{emoji}</div>
  <h1>{title}</h1>
  <div class="meta">
    <span style="color:var(--green);font-weight:700">{tag}</span>
    <span>{date_str}</span>
    <span>· 5 min read</span>
  </div>
</div>

<div class="article-wrap">
  <a href="../blog.html" class="back-link">← All Guides</a>

  {sections_html}

  <div style="margin-top:2.5rem">
    <h2>Recommended Tools</h2>
    <p>Ready to take action? Here are our top picks related to this guide.</p>
    {cta_html}
  </div>

  <div class="disclaimer" style="margin-top:2rem">
    This article is for informational purposes only and does not constitute financial advice. FinanceFlow may earn affiliate commissions from links in this article at no cost to you.
  </div>
</div>

<footer>
  <div class="footer-grid">
    <div class="footer-brand">
      <a class="nav-logo" href="../index.html">Finance<span style="color:#d1fae5">Flow</span></a>
      <p>Free tools and honest advice to help you take control of your money.</p>
    </div>
    <div>
      <h4>Tools</h4>
      <ul>
        <li><a href="../calculator.html">Budget Calculator</a></li>
        <li><a href="../calculator.html">Debt Payoff</a></li>
        <li><a href="../calculator.html">Investment Growth</a></li>
      </ul>
    </div>
    <div>
      <h4>Resources</h4>
      <ul>
        <li><a href="../recommendations.html">Top Picks</a></li>
        <li><a href="../blog.html">All Guides</a></li>
      </ul>
    </div>
    <div>
      <h4>Legal</h4>
      <ul>
        <li><a href="#">Privacy Policy</a></li>
        <li><a href="#">Disclaimer</a></li>
        <li><a href="#">Affiliate Disclosure</a></li>
      </ul>
    </div>
  </div>
  <div class="footer-bottom">
    <span>© {date.today().year} FinanceFlow. All rights reserved.</span>
    <span>Affiliate Disclosure: We may earn commissions from links on this site.</span>
  </div>
</footer>

<script>
  document.getElementById('navToggle').addEventListener('click', () => {{
    document.getElementById('navLinks').classList.toggle('open');
  }});
</script>
</body>
</html>'''


# ── BLOG.HTML UPDATER ─────────────────────────────────────────────────────────
BLOG_START = '<!-- ARTICLES_START -->'
BLOG_END   = '<!-- ARTICLES_END -->'

def build_article_card(article):
    return f'''      <div class="article-card">
        <div class="article-thumb" style="background:{article["bg"]}">{article["emoji"]}</div>
        <div class="article-body">
          <div class="article-meta">
            <span class="article-tag">{article["tag"]}</span>
            <span class="article-date">{article["date"]}</span>
            <span class="article-read-time">· 5 min read</span>
          </div>
          <h2>{article["title"]}</h2>
          <p>{article["desc"]}</p>
          <a href="articles/{article["slug"]}.html" class="article-link">Read Guide →</a>
        </div>
      </div>'''

def update_blog_html(new_articles):
    content = BLOG_FILE.read_text(encoding='utf-8')
    start_idx = content.find(BLOG_START)
    end_idx   = content.find(BLOG_END)
    if start_idx == -1 or end_idx == -1:
        print("WARNING: Could not find ARTICLES_START/END markers in blog.html")
        return

    new_cards = '\n'.join(build_article_card(a) for a in new_articles)
    existing_block = content[start_idx + len(BLOG_START):end_idx]

    updated_block = f'\n{new_cards}\n{existing_block.rstrip()}\n      '
    new_content = (
        content[:start_idx + len(BLOG_START)]
        + updated_block
        + content[end_idx:]
    )
    BLOG_FILE.write_text(new_content, encoding='utf-8')
    print(f"Updated blog.html with {len(new_articles)} new article(s)")


# ── BLOG.HTML FEATURED ARTICLE UPDATER ────────────────────────────────────────
FEATURED_START = '<!-- FEATURED_START -->'
FEATURED_END   = '<!-- FEATURED_END -->'

def update_featured_article(tracking):
    """Replace the featured full article on blog.html with the most recent article."""
    if not tracking:
        return
    latest = tracking[-1]
    content = BLOG_FILE.read_text(encoding='utf-8')
    start_idx = content.find(FEATURED_START)
    end_idx   = content.find(FEATURED_END)
    if start_idx == -1 or end_idx == -1:
        print("WARNING: Could not find FEATURED_START/END markers in blog.html")
        return

    sections_html = ''
    for s in latest.get('sections', []):
        body = md(s['body'])
        sections_html += f'          <h2>{s["h"]}</h2>\n          <p>{body}</p>\n'

    featured_html = f'''<!-- FEATURED_START -->
        <div class="article-full">
          <div class="article-meta" style="margin-bottom:0.75rem">
            <span class="article-tag">{latest["tag"]}</span>
            <span class="article-date">{latest["date"]}</span>
            <span class="article-read-time">· 5 min read</span>
          </div>
          <h1>{latest["title"]}</h1>
          <p>{latest["desc"]}</p>
{sections_html}        </div>
<!-- FEATURED_END -->'''

    new_content = (
        content[:start_idx]
        + featured_html
        + content[end_idx + len(FEATURED_END):]
    )
    BLOG_FILE.write_text(new_content, encoding='utf-8')
    print(f"Updated blog.html featured article: {latest['title']}")


# ── INDEX.HTML LATEST GUIDES UPDATER ───────────────────────────────────────────
INDEX_START = '<!-- INDEX_LATEST_START -->'
INDEX_END   = '<!-- INDEX_LATEST_END -->'

def update_index_html(tracking):
    """Replace the 3-card Latest Guides block on index.html with the 3 most recent articles."""
    if not tracking:
        return
    content = INDEX_FILE.read_text(encoding='utf-8')
    start_idx = content.find(INDEX_START)
    end_idx   = content.find(INDEX_END)
    if start_idx == -1 or end_idx == -1:
        print("WARNING: Could not find INDEX_LATEST_START/END markers in index.html")
        return

    recent = tracking[-3:][::-1]  # last 3 published, newest first
    cards = ''
    for a in recent:
        cards += f'''      <div class="blog-card">
        <div class="blog-thumb" style="background:{a["bg"]}">{a["emoji"]}</div>
        <div class="blog-body">
          <div class="blog-tag">{a["tag"]}</div>
          <h3>{a["title"]}</h3>
          <p>{a["desc"]}</p>
          <a href="articles/{a["slug"]}.html" class="read-more">Read Guide →</a>
        </div>
      </div>\n'''

    new_content = (
        content[:start_idx + len(INDEX_START)]
        + '\n'
        + cards
        + content[end_idx:]
    )
    INDEX_FILE.write_text(new_content, encoding='utf-8')
    print("Updated index.html Latest Guides section")


# ── SITEMAP ────────────────────────────────────────────────────────────────────
def update_sitemap(tracking):
    static_pages = ['', 'calculator', 'recommendations', 'blog']
    urls = []
    for page in static_pages:
        loc = f"{SITE_URL}/{page + '.html' if page else ''}"
        urls.append(f'  <url><loc>{loc}</loc><changefreq>weekly</changefreq><priority>0.8</priority></url>')
    for a in tracking:
        loc = f"{SITE_URL}/articles/{a['slug']}.html"
        urls.append(f'  <url><loc>{loc}</loc><lastmod>{a["date"]}</lastmod><changefreq>never</changefreq><priority>0.6</priority></url>')

    sitemap = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    sitemap += '\n'.join(urls)
    sitemap += '\n</urlset>\n'
    SITEMAP_FILE.write_text(sitemap, encoding='utf-8')
    print(f"Sitemap updated: {len(tracking)} article URLs")


# ── MAIN ───────────────────────────────────────────────────────────────────────
def main():
    ARTICLES_DIR.mkdir(exist_ok=True)
    tracking     = load_tracking()
    new_articles = []

    # 1. Template articles
    topics = pick_topics(tracking, TEMPLATE_PER_RUN)
    for topic in topics:
        article = generate_article(topic)
        art_html = build_article_html(article)
        path    = ARTICLES_DIR / f"{article['slug']}.html"
        path.write_text(art_html, encoding='utf-8')
        tracking.append(article)
        new_articles.append(article)
        print(f'  Template: {article["title"]}')

    # 2. Live news roundup (one per run, skip if already ran today)
    if recent_news_count(tracking) < 1:
        print('  Fetching live news...')
        stories = get_news_stories()
        news_article = build_news_article(stories)
        if news_article:
            art_html = build_article_html(news_article)
            path = ARTICLES_DIR / f"{news_article['slug']}.html"
            path.write_text(art_html, encoding='utf-8')
            tracking.append(news_article)
            new_articles.append(news_article)
            print(f'  News: {news_article["title"]}')
        else:
            print('  Skipped news roundup (no stories fetched)')
    else:
        print('  Skipped news roundup (already published today)')

    update_blog_html(new_articles)
    update_featured_article(tracking)
    update_index_html(tracking)
    update_sitemap(tracking)
    save_tracking(tracking)
    print(f'\nDone. {len(new_articles)} article(s) published.')

if __name__ == '__main__':
    main()

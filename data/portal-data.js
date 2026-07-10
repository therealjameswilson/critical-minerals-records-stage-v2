window.CRITICAL_MINERALS_PORTAL = {
  eras: [
    {
      id: "civil-war",
      label: "Civil War",
      years: "1861-1865",
      start: 1861,
      end: 1865,
      question: "How did blockade, wartime procurement, and industrial mobilization affect access to metals?",
      status: "research"
    },
    {
      id: "industrial-expansion",
      label: "Industrial Expansion",
      years: "1866-1897",
      start: 1866,
      end: 1897,
      question: "How did industrial scale, rail networks, and overseas markets alter material demand?",
      status: "research"
    },
    {
      id: "spanish-american-war",
      label: "Spanish-American War",
      years: "1898-1901",
      start: 1898,
      end: 1901,
      question: "What did overseas war reveal about logistics, metals, and strategic access?",
      status: "research"
    },
    {
      id: "world-war-i",
      label: "World War I",
      years: "1902-1918",
      start: 1902,
      end: 1918,
      question: "Which raw-material bottlenecks entered U.S. wartime planning and diplomacy?",
      status: "research"
    },
    {
      id: "interwar",
      label: "Interwar",
      years: "1919-1938",
      start: 1919,
      end: 1938,
      question: "How did officials turn wartime shortages into national mineral planning?",
      status: "research"
    },
    {
      id: "world-war-ii",
      label: "World War II",
      years: "1939-1945",
      start: 1939,
      end: 1945,
      question: "How did procurement, substitution, and allied access shape the strategic-materials system?",
      status: "research"
    },
    {
      id: "early-cold-war",
      label: "Early Cold War",
      years: "1946-1960",
      start: 1946,
      end: 1960,
      question: "How did stockpiling, European recovery, and decolonization redefine accessible supply?",
      status: "seeded"
    },
    {
      id: "cold-war",
      label: "Cold War",
      years: "1961-1991",
      start: 1961,
      end: 1991,
      question: "How did alliance geography, political reliability, and strategic planning change material access?",
      status: "seeded"
    },
    {
      id: "post-cold-war",
      label: "Post-Cold War",
      years: "1992-2000",
      start: 1992,
      end: 2000,
      question: "How did reduced stockpiles and expanding global trade change the U.S. risk model?",
      status: "research"
    },
    {
      id: "china-wto-era",
      label: "China WTO Era",
      years: "2001-2016",
      start: 2001,
      end: 2016,
      question: "Where did extraction, processing, refining, and manufacturing become concentrated?",
      status: "research"
    },
    {
      id: "critical-minerals-strategy",
      label: "Critical Minerals Strategy",
      years: "2017-2024",
      start: 2017,
      end: 2024,
      question: "How did criticality lists, energy technologies, and supply-chain risk reshape policy?",
      status: "seeded"
    },
    {
      id: "ministerial-era",
      label: "Ministerial Era",
      years: "2025-present",
      start: 2025,
      end: 2026,
      question: "How is modern minerals diplomacy connecting agreements, finance, processing, and partner coordination?",
      status: "seeded"
    }
  ],
  minerals: [
    { name: "Lithium", symbol: "Li", prompt: "Trace lithium suppliers, battery policy, trade records, and agreements over time." },
    { name: "Cobalt", symbol: "Co", prompt: "Compare wartime cobalt access with Cold War and modern battery supply diplomacy." },
    { name: "Copper", symbol: "Cu", prompt: "Follow copper through wartime requirements, Chilean relations, trade, and infrastructure." },
    { name: "Graphite", symbol: "C", prompt: "Connect historical strategic-material lists to modern anode and processing concerns." },
    { name: "Rare earth elements", symbol: "REE", prompt: "Map the shift from geological resource to processing and manufacturing vulnerability." },
    { name: "Nickel", symbol: "Ni", prompt: "Examine alloy demand, stockpiling, supplier geography, and processing capacity." },
    { name: "Manganese", symbol: "Mn", prompt: "Track steel, batteries, stockpile assumptions, and changing foreign sources." },
    { name: "Gallium", symbol: "Ga", prompt: "Review semiconductor uses, trade-code caveats, and current supply restrictions." },
    { name: "Germanium", symbol: "Ge", prompt: "Connect defense and semiconductor demand to stockpiling and trade evidence." },
    { name: "Antimony", symbol: "Sb", prompt: "Trace defense use, stockpile policy, and shifting overseas supply." },
    { name: "Tin", symbol: "Sn", prompt: "Follow Southeast Asian supply, wartime planning, and modern electronics demand." },
    { name: "Tungsten", symbol: "W", prompt: "Compare machining and armament requirements across war and peacetime planning." },
    { name: "Chromium", symbol: "Cr", prompt: "Map chromite access, alloy demand, stockpile assumptions, and supplier reliability." }
  ],
  countries: [
    { name: "United States", lon: -98, lat: 39, focus: "Policy, demand, stockpiling, trade, and domestic capacity" },
    { name: "Canada", lon: -106, lat: 56, focus: "Allied access, mining, processing, and defense supply" },
    { name: "Mexico", lon: -102, lat: 23, focus: "North American supply chains and historical accessibility" },
    { name: "Chile", lon: -71, lat: -33, focus: "Copper, lithium, investment, and diplomatic agreements" },
    { name: "Argentina", lon: -64, lat: -34, focus: "Lithium, investment climate, and infrastructure" },
    { name: "Brazil", lon: -52, lat: -10, focus: "Niobium, graphite, rare earths, and industrial partnership" },
    { name: "Peru", lon: -75, lat: -9, focus: "Copper, mining policy, infrastructure, and investment" },
    { name: "Democratic Republic of the Congo", lon: 23, lat: -3, focus: "Cobalt, copper, historical access, and governance" },
    { name: "Egypt", lon: 30, lat: 27, focus: "Commercial diplomacy, infrastructure, trade corridors, and regional security" },
    { name: "Ethiopia", lon: 40, lat: 9, focus: "Strategic investment, infrastructure corridors, and commercial engagement" },
    { name: "Kenya", lon: 38, lat: 1, focus: "Rare-earth potential, investment climate, infrastructure, and regional diplomacy" },
    { name: "Djibouti", lon: 43, lat: 12, focus: "Port infrastructure, maritime access, security, and commercial ties" },
    { name: "South Africa", lon: 24, lat: -30, focus: "Chromium, manganese, platinum-group metals, and historical access" },
    { name: "Namibia", lon: 17, lat: -22, focus: "Uranium, rare earths, investment, and infrastructure" },
    { name: "Greenland", lon: -42, lat: 72, focus: "Arctic strategy, rare earths, and alliance geography" },
    { name: "Ukraine", lon: 31, lat: 49, focus: "Reconstruction, titanium, graphite, and strategic partnership" },
    { name: "Kazakhstan", lon: 68, lat: 48, focus: "Uranium, chromium, rare earths, and transport corridors" },
    { name: "Uzbekistan", lon: 64, lat: 41, focus: "Critical minerals, investment, and Central Asian connectivity" },
    { name: "Indonesia", lon: 118, lat: -2, focus: "Nickel, processing policy, investment, and trade" },
    { name: "Philippines", lon: 122, lat: 13, focus: "Nickel, alliances, maritime access, and investment" },
    { name: "Mongolia", lon: 103, lat: 46, focus: "Rare earths, copper, third-neighbor diplomacy, and infrastructure" },
    { name: "Australia", lon: 134, lat: -25, focus: "Allied mining, processing, investment, and defense supply chains" }
  ],
  administrations: [
    { label: "Lincoln", start: 1861, end: 1865 },
    { label: "Grant", start: 1869, end: 1877 },
    { label: "Theodore Roosevelt", start: 1901, end: 1909 },
    { label: "Wilson", start: 1913, end: 1921 },
    { label: "Franklin D. Roosevelt", start: 1933, end: 1945 },
    { label: "Truman", start: 1945, end: 1953 },
    { label: "Eisenhower", start: 1953, end: 1961 },
    { label: "Kennedy", start: 1961, end: 1963 },
    { label: "Johnson", start: 1963, end: 1969 },
    { label: "Nixon", start: 1969, end: 1974 },
    { label: "Ford", start: 1974, end: 1977 },
    { label: "Carter", start: 1977, end: 1981 },
    { label: "Reagan", start: 1981, end: 1989 },
    { label: "George H. W. Bush", start: 1989, end: 1993 },
    { label: "Clinton", start: 1993, end: 2001 },
    { label: "George W. Bush", start: 2001, end: 2009 },
    { label: "Obama", start: 2009, end: 2017 },
    { label: "Trump I", start: 2017, end: 2021 },
    { label: "Biden", start: 2021, end: 2025 },
    { label: "Trump II", start: 2025, end: 2026 }
  ],
  sources: [
    { name: "FRUS", role: "Diplomatic decisions, negotiations, policy assumptions, and historical context", tier: "Primary edited record" },
    { name: "NARA", role: "Archival discovery across record groups, presidential libraries, maps, photographs, and finding aids", tier: "Primary catalog metadata" },
    { name: "Census", role: "Imports and exports by commodity code, partner, flow, and period", tier: "Official statistical data" },
    { name: "USGS", role: "Commodity statistics, import reliance, production, criticality, and geoscience", tier: "Official scientific data" },
    { name: "State", role: "Current diplomacy, agreements, ministerials, releases, and investment climate", tier: "Official policy record" },
    { name: "DLA", role: "National Defense Stockpile and strategic-material program context", tier: "Official program record" }
  ],
  commandCenter: {
    report: {
      title: "Deputy Secretary Landau and the Critical Minerals Imperative",
      url: "https://github.com/therealjameswilson/critical-minerals-records-stage/blob/main/research/Landau-Critical-Minerals-2026.md",
      lines: 191,
      references: 31,
      tier: "Analytical synthesis",
      caveat: "The report combines official records, partner-government material, commercial reporting, and outside analysis. Validate operational claims against the linked primary source."
    },
    timeline: [
      {
        date: "Jan. 14",
        title: "Processed-minerals proclamation",
        detail: "The White House treated processed critical-mineral imports as a national-security issue and directed negotiated adjustment measures.",
        source: "White House",
        url: "https://www.whitehouse.gov/presidential-actions/2026/01/adjusting-imports-of-processed-critical-minerals-and-their-derivative-products-into-the-united-states/"
      },
      {
        date: "Jan. 24-Feb. 1",
        title: "Landau Africa travel",
        detail: "An official State itinerary covered Egypt, Ethiopia, Kenya, and Djibouti immediately before the ministerial.",
        source: "State",
        url: "https://www.state.gov/releases/office-of-the-spokesperson/2026/01/deputy-secretary-landaus-travel-to-egypt-ethiopia-kenya-and-djibouti"
      },
      {
        date: "Feb. 4",
        title: "Critical Minerals Ministerial",
        detail: "The ministerial connected bilateral frameworks, project finance, allied coordination, and an industry implementation task force.",
        source: "State",
        url: "https://www.state.gov/releases/office-of-the-spokesperson/2026/02/2026-critical-minerals-ministerial"
      },
      {
        date: "Feb. 18",
        title: "Uzbekistan investment framework",
        detail: "DFC announced a proposed joint framework spanning exploration, extraction, processing, infrastructure, and energy.",
        source: "DFC",
        url: "https://www.dfc.gov/media/press-releases/dfc-leadership-lays-foundation-investment-partnership-uzbekistan"
      },
      {
        date: "May 29",
        title: "National-security investment workforce",
        detail: "The White House authorized critical-position pay for up to 400 investment, engineering, finance, and legal specialists.",
        source: "White House",
        url: "https://www.whitehouse.gov/presidential-actions/2026/05/approving-critical-position-pay-authority-for-national-security-investment-workforce/"
      }
    ],
    workstreams: [
      { label: "Agreements", detail: "Track the instrument, responsible offices, consultations, deadlines, and implementation status." },
      { label: "Projects", detail: "Identify bankable projects, ownership, offtake, infrastructure, permitting, and political risk." },
      { label: "Finance", detail: "Map DFC, EXIM, allied, host-government, and private-capital roles across the value chain." },
      { label: "Post reporting", detail: "Report regulatory barriers, local politics, community effects, security risks, and partner follow-through." }
    ],
    historicalLinks: [
      {
        modern: "Agreements linked to investment",
        historical: "1947 ERP planning paired bilateral commitments with production support and U.S. stockpiling.",
        recordId: "frus-1947-v1-d395-strategic-materials"
      },
      {
        modern: "Mineral-rich Africa as strategic geography",
        historical: "A 1953 estimate connected raw-material access, infrastructure, political change, and Western strategy.",
        recordId: "frus-1952-54-v11p1-d27-tropical-africa"
      },
      {
        modern: "Assessing reliable foreign supply",
        historical: "A 1967 stockpile debate assigned State a role in judging the political and economic dependability of sources.",
        recordId: "frus-1964-68-v9-d344-stockpile-objectives"
      }
    ],
    partners: ["Argentina", "Chile", "Democratic Republic of the Congo", "Kazakhstan", "Mexico", "Uzbekistan"]
  },
  searchPrompts: [
    "cobalt during the early Cold War",
    "strategic materials stockpiling",
    "Tropical Africa cobalt copper",
    "Chile copper trade",
    "rare earth elements 2025",
    "FRUS accessible foreign sources"
  ]
};

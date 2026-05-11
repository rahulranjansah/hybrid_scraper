# smoke_predictions.jsonl



- Rows: **6**

- Human flags: {'green': 2, 'yellow': 2, 'red': 2}

- Judge predictions: {'yellow': 2, 'red': 3, 'green': 1}

- Agreement: **2/6** = 33.3%



### 1. Yukiko Yamada
- **Human:** 🟢 green  ·  **Judge:** 🟡 yellow  ·  ❌ mismatch
- Judge tags: `clean_long_tenure, level_matches_brief, multinational_hr_experience, sector_mismatch`
- Judge reason: Yukiko has extensive HR leadership experience in multinational environments, including 8+ years in her current role, but her industry background is in financial services and healthcare, not retail.

### 2. Shiho Saito
- **Human:** 🟢 green  ·  **Judge:** 🟡 yellow  ·  ❌ mismatch
- Judge tags: `bilingual_en_ja, clean_long_tenure, level_matches_brief, multinational_hr_experience, sector_mismatch`
- Judge reason: Shiho has strong multinational HRBP experience and long tenure, but her background is in legal and pharma, not the preferred retail/consumer goods sector.

### 3. Shingo Ono
- **Human:** 🟡 yellow  ·  **Judge:** 🔴 red  ·  ❌ mismatch
- Judge tags: `clean_long_tenure, level_too_senior_for_brief, multinational_hr_experience, sector_mismatch`
- Judge reason: Shingo has extensive HR leadership experience, but his current role as a Business Division General Manager and his overall career trajectory suggest he is too senior for an HR Manager role, and his industry experience is in chemical manufacturing, not consumer goods.
- Red routing: `red_permanent`

### 4. Yoko Sato
- **Human:** 🟡 yellow  ·  **Judge:** 🟢 green  ·  ❌ mismatch
- Judge tags: `bilingual_en_ja, clean_long_tenure, level_matches_brief, multinational_hr_experience`
- Judge reason: Yoko has 17+ years of HR experience in global companies, aligning well with the HR Manager brief, and her profile indicates strong HRBP and strategic HR skills.

### 5. Tatsuo Kinoshita
- **Human:** 🔴 red  ·  **Judge:** 🔴 red  ·  ✅ match
- Judge tags: `clean_long_tenure, level_too_senior_for_brief, multinational_hr_experience`
- Judge reason: Tatsuo is a CHRO at Panasonic Holdings with 27 years of experience, making him significantly overqualified for an HR Manager role.
- Red routing: `red_permanent`

### 6. Shinichiroh Yamamoto
- **Human:** 🔴 red  ·  **Judge:** 🔴 red  ·  ✅ match
- Judge tags: `level_too_senior_for_brief, multinational_hr_experience, recently_joined, relevant_industry_adjacency`
- Judge reason: Shinichiroh has extensive HR leadership experience in multinational tech and entertainment companies, but his background as a CHRO/Head of HR is too senior for this HR Manager brief, and he recently joined his current role at Google.
- Red routing: `red_permanent`
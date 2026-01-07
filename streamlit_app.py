import streamlit as st
import re
from num2words import num2words

# --- Configuration ---
WORDS_TO_IGNORE_IN_NUMBERS = {"hundred", "thousand", "and"}
FRAMES_PER_SECOND = 25
MONTHS = ["january", "february", "march", "april", "may", "june",
          "july", "august", "september", "october", "november", "december"]

# --- Core Logic ---

def convert_number_smart(number_val):
    """Smart logic to handle specific number ranges for ad clearance."""
    if 1100 <= number_val <= 1999:
        hundreds = number_val // 100
        remainder = number_val % 100
        text = f"{num2words(hundreds)} hundred"
        if remainder > 0:
            text += f" and {num2words(remainder)}"
        return text
    if 2010 <= number_val <= 2099:
        return num2words(number_val, to='year')
    return num2words(number_val)

def clean_and_tokenize(text, exclusions=""):
    """
    Splits text while respecting Clearcast 'interpretation' rules:
    1. Abbreviations (T&Cs, p.a., ROI) -> 1 word
    2. Postcodes -> 2 words
    3. URLs -> 1 word
    4. Brand Names -> Removed (0 words)
    """
    if not text:
        return []

    # 1. Remove Brand Names / Exclusions first
    if exclusions:
        exclusion_list = [e.strip() for e in exclusions.split(',')]
        for excl in exclusion_list:
            if excl:
                # Case-insensitive removal of exact phrases
                pattern = re.compile(re.escape(excl), re.IGNORECASE)
                text = pattern.sub(" ", text)

    # 2. Protect URLs (replace with placeholder token)
    url_regex = r'(?:https?://)?(?:www\.)?([a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}(?:/[^\s]*)?'
    text = re.sub(url_regex, 'TOKEN_URL', text)

    # 3. Protect Postcodes (UK Format) -> Replace with 2 tokens
    # Matches: SW1A 1AA, M1 1AA, etc.
    postcode_regex = r'\b[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}\b'
    text = re.sub(postcode_regex, 'TOKEN_POSTCODE_1 TOKEN_POSTCODE_2', text, flags=re.IGNORECASE)

    # 4. Protect Common Abbreviations -> Replace with single token
    # T&Cs, p.a., ROI, etc.
    abbreviations = [
        (r'\bT&Cs\b', 'TOKEN_ABBREV'),
        (r'\bT\s?&\s?Cs\b', 'TOKEN_ABBREV'), # Handles T & Cs
        (r'\bp\.?a\.?\b', 'TOKEN_ABBREV'),   # Handles p.a.
        (r'\bR\.?O\.?I\.?\b', 'TOKEN_ABBREV'), # Handles ROI
    ]
    for pattern, token in abbreviations:
        text = re.sub(pattern, token, text, flags=re.IGNORECASE)

    # 5. Split remaining text by numbers to process them
    parts = re.split(r'(\d+)', text)
    
    final_tokens = []
    
    for part in parts:
        if part.isdigit():
            # Convert number to words
            spoken_number = convert_number_smart(int(part))
            # Tokenize the spoken number
            words = re.findall(r'\b\w+\b', spoken_number.lower())
            # Remove invisible counters (hundred, thousand, and)
            valid_words = [w for w in words if w not in WORDS_TO_IGNORE_IN_NUMBERS]
            final_tokens.extend(valid_words)
        else:
            # Standard tokenizer for text parts
            # matches words or our specific TOKEN_ strings
            words = re.findall(r'\b[\w&]+\b', part)
            final_tokens.extend(words)

    return final_tokens

def calculate_duration(word_count):
    if word_count == 0:
        return 0, 0
    
    rt = 3.0 if word_count >= 10 else 2.0
    # Formula: (Words * 0.2) + Recognition Time
    duration = (word_count * 0.2) + rt
    return duration, rt

# --- Streamlit UI ---

st.set_page_config(page_title="Clearcast Calculator", layout="wide")
st.title("Clearcast Disclaimer Calculator")
st.markdown("""
This tool calculates hold duration based on **Clearcast & BCAP** guidance.
**V1.5 Updates:**
* **Abbreviations:** 'T&Cs', 'p.a.', 'ROI' count as **1 word**.
* **Postcodes:** Count as **2 words**.
* **Brand Names:** Can be excluded from the count.
""")

col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("Input")
    main_text = st.text_area("Disclaimer Text", height=150, help="Enter the legal text here.")
    
    with st.expander("Exclusions & Options"):
        brand_exclusions = st.text_input("Brand Names to Exclude (comma separated)", 
                                         help="E.g. 'Nike, Adidas'. These words will not be counted.")
        has_additional = st.checkbox("Include Additional/Split Text?")
    
    add_text = ""
    if has_additional:
        st.info("Additional text appearing at a different time:")
        add_text = st.text_area("Additional Text", height=100)

    calc_btn = st.button("Calculate Duration", type="primary")

with col2:
    st.subheader("Results")

    if calc_btn and (main_text or add_text):
        # 1. Tokenize Main
        main_tokens = clean_and_tokenize(main_text, brand_exclusions)
        # De-duplicate MAIN text (Standard rule: unique words only)
        # Note: We maintain order for display but use set for counting if required. 
        # *However*, usually duration is based on unique words in the block.
        # Let's use the standard "Unique Words" approach.
        main_unique = []
        seen = set()
        for w in main_tokens:
            w_lower = w.lower()
            if w_lower not in seen:
                seen.add(w_lower)
                main_unique.append(w)
        
        main_wc = len(main_unique)
        main_dur, main_rt = calculate_duration(main_wc)

        # 2. Tokenize Additional
        add_dur, add_wc, add_rt = 0, 0, 0
        add_unique_new = []
        
        if has_additional and add_text:
            add_tokens = clean_and_tokenize(add_text, brand_exclusions)
            # Filter out words already counted in Main
            main_set_lower = {t.lower() for t in main_unique}
            
            for w in add_tokens:
                if w.lower() not in main_set_lower and w.lower() not in seen:
                    seen.add(w.lower())
                    add_unique_new.append(w)
            
            add_wc = len(add_unique_new)
            add_dur, add_rt = calculate_duration(add_wc)

        total_dur = main_dur + add_dur

        # --- Display ---
        st.metric(label="Total Duration", value=f"{total_dur:.1f}s")
        if total_dur > 0:
            whole_sec = int(total_dur)
            frames = round((total_dur - whole_sec) * FRAMES_PER_SECOND)
            st.caption(f"({whole_sec} seconds and {frames} frames)")
        
        st.divider()
        
        # Breakdown
        if main_wc > 0:
            st.write(f"**Main Text:** {main_wc} words ({main_dur:.1f}s)")
            with st.expander("View Counted Words"):
                st.write(", ".join(main_unique))
        
        if add_wc > 0:
            st.write(f"**Additional Text:** {add_wc} words ({add_dur:.1f}s)")
            with st.expander("View New Unique Words"):
                st.write(", ".join(add_unique_new))

    elif calc_btn:
        st.warning("Please enter text.")

# --- Optimization Tips ---
st.markdown("---")
st.subheader("Smart Optimization Tips")
tips = []
full_text = (main_text + " " + add_text)

if "Terms and Conditions" in full_text:
    tips.append("**Huge Saving:** Change 'Terms and Conditions' (3 words) to 'T&Cs' (1 word). Saves 0.4s.")
if "per annum" in full_text.lower():
    tips.append("**Quick Fix:** Change 'per annum' (2 words) to 'p.a.' (1 word). Saves 0.2s.")
if "Republic of Ireland" in full_text:
    tips.append("**Quick Fix:** Change 'Republic of Ireland' (3 words) to 'ROI' (1 word). Saves 0.4s.")

if tips and (main_text or add_text):
    for tip in tips:
        st.info(tip)
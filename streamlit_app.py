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
    """
    Smart logic to handle specific number ranges for ad clearance.
    """
    # Range 1: 1100 - 1999 (The "Teen Hundreds" Fix)
    if 1100 <= number_val <= 1999:
        hundreds = number_val // 100
        remainder = number_val % 100
        text = f"{num2words(hundreds)} hundred"
        if remainder > 0:
            text += f" and {num2words(remainder)}"
        return text
        
    # Range 2: 2010 - 2099 (Modern Years)
    if 2010 <= number_val <= 2099:
        return num2words(number_val, to='year')
        
    # Range 3: Standard
    return num2words(number_val)

def clean_and_tokenize(text, exclusions=""):
    """
    Splits text while respecting Clearcast 'interpretation' rules.
    Standardizes abbreviations like Ts&Cs -> T&Cs for consistent counting.
    """
    if not text:
        return []

    # 1. Remove Brand Names / Exclusions first
    if exclusions:
        exclusion_list = [e.strip() for e in exclusions.split(',')]
        for excl in exclusion_list:
            if excl:
                pattern = re.compile(re.escape(excl), re.IGNORECASE)
                text = pattern.sub(" ", text)

    # 2. Map of Patterns to Safe Tokens (to preserve 1-word count)
    # We use temporary tokens (SAFE_TOKEN_X) to ensure they survive splitting, 
    # then map them back to readable text later.
    token_map = {
        'SAFE_TOKEN_URL': '[URL]',
        'SAFE_TOKEN_TCS': 'T&Cs',
        'SAFE_TOKEN_PA': 'p.a.',
        'SAFE_TOKEN_ROI': 'ROI',
        'SAFE_TOKEN_NI': 'NI',
        # Postcodes are special (count as 2), we leave them to natural split 
        # but ensure they have a space so "SW1A1AA" becomes "SW1A 1AA".
    }

    # 3. Protect URLs
    url_regex = r'(?:https?://)?(?:www\.)?([a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}(?:/[^\s]*)?'
    text = re.sub(url_regex, 'SAFE_TOKEN_URL', text)

    # 4. Protect Postcodes (UK Format) -> Ensure space exists
    # Matches SW1A 1AA or SW1A1AA. Replaces with "SW1A 1AA" to ensure 2-word count.
    # Note: We rely on the natural split later to count this as 2 words.
    postcode_regex = r'\b([A-Z]{1,2}\d[A-Z\d]?)\s*(\d[A-Z]{2})\b'
    text = re.sub(postcode_regex, r'\1 \2', text, flags=re.IGNORECASE)

    # 5. Protect Abbreviations (Replace with SAFE_TOKENS)
    abbreviations = [
        # Matches: T&Cs, Ts&Cs, T & Cs, Ts & Cs
        (r'\bTs?\s?&\s?Cs\b', 'SAFE_TOKEN_TCS'), 
        (r'\bp\.?a\.?\b', 'SAFE_TOKEN_PA'),
        (r'\bR\.?O\.?I\.?\b', 'SAFE_TOKEN_ROI'),
        (r'\bN\.?I\.?\b', 'SAFE_TOKEN_NI'),
    ]
    for pattern, token in abbreviations:
        text = re.sub(pattern, token, text, flags=re.IGNORECASE)

    # 6. Split text by numbers to process them
    parts = re.split(r'(\d+)', text)
    
    final_tokens = []
    
    for part in parts:
        if part.isdigit():
            # Convert number to words
            spoken_number = convert_number_smart(int(part))
            words = re.findall(r'\b\w+\b', spoken_number.lower())
            valid_words = [w for w in words if w not in WORDS_TO_IGNORE_IN_NUMBERS]
            final_tokens.extend(valid_words)
        else:
            # Tokenize text. We include '_' to catch our SAFE_TOKENS.
            # We also include '&' so legitimate "Q&A" might survive if needed, 
            # though T&Cs is already handled.
            raw_tokens = re.findall(r'\b[\w&]+\b', part)
            
            # Swap Tokens back to Readable Text
            for t in raw_tokens:
                if t in token_map:
                    final_tokens.append(token_map[t])
                else:
                    final_tokens.append(t)

    return final_tokens

def calculate_duration(word_count):
    if word_count == 0:
        return 0, 0
    
    rt = 3.0 if word_count >= 10 else 2.0
    duration = (word_count * 0.2) + rt
    return duration, rt

# --- Streamlit UI ---

st.set_page_config(page_title="Clearcast Calculator", layout="wide")

st.title("Clearcast Disclaimer Calculator")
st.markdown("""
This tool calculates hold duration based on **Clearcast & BCAP** guidance.
**V1.6 Updates:**
* **Correct Display:** 'T&Cs', 'p.a.' appear correctly in the word list.
* **Smarter Matching:** Handles 'Ts&Cs', 'T & Cs' automatically.
""")

col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("Input")
    main_text = st.text_area("Disclaimer Text (Main)", height=150, help="Enter the main legal text here.")
    
    with st.expander("Exclusions & Options"):
        brand_exclusions = st.text_input("Brand Names to Exclude (comma separated)", 
                                         help="E.g. 'Nike, Adidas'. These words will not be counted.")
        has_additional = st.checkbox("Include Additional/Split Text?")
    
    add_text = ""
    if has_additional:
        st.info("Enter any additional text that appears at a different time while the disclaimer is held.")
        add_text = st.text_area("Additional Text", height=100)

    calc_btn = st.button("Calculate Duration", type="primary")

with col2:
    st.subheader("Results")

    if calc_btn and (main_text or add_text):
        # 1. Tokenize Main
        main_tokens = clean_and_tokenize(main_text, brand_exclusions)
        
        # De-duplicate MAIN text (Case-insensitive)
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

        # --- Display Results ---
        st.metric(label="Total Duration", value=f"{total_dur:.1f}s")
        
        if total_dur > 0:
            whole_sec = int(total_dur)
            frames = round((total_dur - whole_sec) * FRAMES_PER_SECOND)
            st.caption(f"({whole_sec} seconds and {frames} frames)")
        
        st.divider()
        
        # Breakdowns
        if main_wc > 0:
            with st.expander("Main Disclaimer Breakdown", expanded=True):
                st.write(f"**Sub-Total:** {main_dur:.1f}s")
                st.write(f"- Unique Words: {main_wc}")
                st.write(f"- Text Hold: {main_wc * 0.2:.1f}s")
                st.write(f"- Recognition: {main_rt:.1f}s")
                st.caption(f"Countable Words: {', '.join(main_unique)}")
        
        if add_wc > 0:
            with st.expander("Additional Text Breakdown", expanded=True):
                st.write(f"**Sub-Total:** {add_dur:.1f}s")
                st.write(f"- New Unique Words: {add_wc}")
                st.write(f"- Text Hold: {add_wc * 0.2:.1f}s")
                st.write(f"- Recognition: {add_rt:.1f}s")
                st.caption(f"Countable Words: {', '.join(add_unique_new)}")

    elif calc_btn:
        st.warning("Please enter some text to calculate.")

# --- Optimization Tips ---
st.markdown("---")
st.subheader("Smart Optimization Tips")
tips = []
full_text = (main_text + " " + add_text)
full_text_lower = full_text.lower()

# Check for optimization opportunities
if "Terms and Conditions" in full_text:
    tips.append("**Huge Saving:** Change 'Terms and Conditions' (3 words) to 'T&Cs' (1 word). Saves 0.4s.")

if "per annum" in full_text_lower:
    tips.append("**Quick Fix:** Change 'per annum' (2 words) to 'p.a.' (1 word). Saves 0.2s.")

if "republic of ireland" in full_text_lower:
    tips.append("**Quick Fix:** Change 'Republic of Ireland' (3 words) to 'ROI' (1 word). Saves 0.4s.")

if any(month in full_text_lower for month in MONTHS):
    tips.append("**Formatting:** Writing dates out in full (e.g. 'January') is lengthy. Consider using numerals (e.g., '25.01.25').")

if "per week" in full_text_lower or "per month" in full_text_lower:
     tips.append("**Formatting:** Use '/week' or '/month' instead of 'per week'/'per month' to save a word.")

if tips and (main_text or add_text):
    for tip in tips:
        st.info(tip, icon="💡")
elif (main_text or add_text):
    st.success("No obvious optimizations found. Good job!", icon="✅")

# Footer
st.markdown("---")
st.caption("This tool is for guidance only. Always verify with Clearcast.")
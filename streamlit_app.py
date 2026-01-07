import streamlit as st
import re
from num2words import num2words

# --- Configuration ---
WORDS_TO_IGNORE_IN_NUMBERS = {"hundred", "thousand", "and"}
FRAMES_PER_SECOND = 25
MONTHS = ["january", "february", "march", "april", "may", "june",
          "july", "august", "september", "october", "november", "december"]
# specific words to watch for tips
SYMBOL_WORDS = ["percent", "pounds", "euros"] 

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

def extract_tokens(text, exclusions=""):
    """Parses text into text_tokens and number_strings."""
    if not text:
        return [], []

    # 1. Remove Brand Names / Exclusions
    if exclusions:
        exclusion_list = [e.strip() for e in exclusions.split(',')]
        for excl in exclusion_list:
            if excl:
                pattern = re.compile(re.escape(excl), re.IGNORECASE)
                text = pattern.sub(" ", text)

    # 2. Map of Patterns to Safe Tokens
    token_map = {
        'SAFE_TOKEN_URL': '[URL]',
        'SAFE_TOKEN_TCS': 'T&Cs',
        'SAFE_TOKEN_PA': 'p.a.',
        'SAFE_TOKEN_ROI': 'ROI',
        'SAFE_TOKEN_NI': 'NI',
    }

    # 3. Protect URLs
    url_regex = r'(?:https?://)?(?:www\.)?([a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}(?:/[^\s]*)?'
    text = re.sub(url_regex, 'SAFE_TOKEN_URL', text)

    # 4. Protect Postcodes
    postcode_regex = r'\b([A-Z]{1,2}\d[A-Z\d]?)\s*(\d[A-Z]{2})\b'
    text = re.sub(postcode_regex, r'\1 \2', text, flags=re.IGNORECASE)

    # 5. Protect Abbreviations
    abbreviations = [
        (r'\bTs?\s?&\s?Cs\b', 'SAFE_TOKEN_TCS'), 
        (r'\bp\.?a\.?\b', 'SAFE_TOKEN_PA'),
        (r'\bR\.?O\.?I\.?\b', 'SAFE_TOKEN_ROI'),
        (r'\bN\.?I\.?\b', 'SAFE_TOKEN_NI'),
    ]
    for pattern, token in abbreviations:
        text = re.sub(pattern, token, text, flags=re.IGNORECASE)

    # 6. Split text by numbers
    parts = re.split(r'(\d+)', text)
    
    text_tokens = []
    number_strings = []
    
    for part in parts:
        if part.isdigit():
            number_strings.append(part)
        else:
            raw_tokens = re.findall(r'\b[\w&]+\b', part)
            for t in raw_tokens:
                if t in token_map:
                    text_tokens.append(token_map[t])
                else:
                    text_tokens.append(t)

    return text_tokens, number_strings

def calculate_word_lists(text_tokens, number_strings):
    """Counts logic: Text (unique words), Numbers (unique number strings)."""
    final_display_list = []
    
    # 1. Process Manual Text
    unique_text = []
    seen_text = set()
    for w in text_tokens:
        w_lower = w.lower()
        if w_lower not in seen_text:
            seen_text.add(w_lower)
            unique_text.append(w)
            final_display_list.append(w)
            
    # 2. Process Numbers
    seen_numbers = set()
    number_words_count = 0
    
    for num_str in number_strings:
        if num_str not in seen_numbers:
            seen_numbers.add(num_str)
            spoken = convert_number_smart(int(num_str))
            words = re.findall(r'\b\w+\b', spoken.lower())
            valid_words = [w for w in words if w not in WORDS_TO_IGNORE_IN_NUMBERS]
            number_words_count += len(valid_words)
            final_display_list.extend(valid_words)
            
    total_count = len(unique_text) + number_words_count
    return total_count, final_display_list

def calculate_duration(word_count):
    if word_count == 0:
        return 0, 0
    rt = 3.0 if word_count >= 10 else 2.0
    duration = (word_count * 0.2) + rt
    return duration, rt

# --- Streamlit UI ---

st.set_page_config(page_title="Clearcast Calculator", layout="wide")

st.title("Clearcast Disclaimer Calculator")
st.markdown("This tool calculates hold duration based on **Clearcast & BCAP** guidance.")

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
        st.info("Enter any additional text that appears at a different time.")
        add_text = st.text_area("Additional Text", height=100)

    calc_btn = st.button("Calculate Duration", type="primary")

# Variables to hold results for tips section
main_wc, main_dur, main_rt = 0, 0, 0
add_wc, add_dur, add_rt = 0, 0, 0

with col2:
    st.subheader("Results")

    if calc_btn and (main_text or add_text):
        # 1. Process Main
        main_text_tokens, main_num_strings = extract_tokens(main_text, brand_exclusions)
        main_wc, main_display_list = calculate_word_lists(main_text_tokens, main_num_strings)
        main_dur, main_rt = calculate_duration(main_wc)

        # 2. Process Additional
        add_display_list = []
        if has_additional and add_text:
            add_text_tokens, add_num_strings = extract_tokens(add_text, brand_exclusions)
            # Filter against Main
            main_text_set = {t.lower() for t in main_text_tokens}
            unique_add_tokens = [t for t in add_text_tokens if t.lower() not in main_text_set]
            
            main_num_set = set(main_num_strings)
            unique_add_nums = [n for n in add_num_strings if n not in main_num_set]
            
            add_wc, add_display_list = calculate_word_lists(unique_add_tokens, unique_add_nums)
            add_dur, add_rt = calculate_duration(add_wc)

        total_dur = main_dur + add_dur

        # --- Display ---
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
                st.write(f"- Counted Words: {main_wc}")
                st.write(f"- Text Hold: {main_wc * 0.2:.1f}s")
                st.write(f"- Recognition: {main_rt:.1f}s")
                st.caption(f"Breakdown: {', '.join(main_display_list)}")
        
        if add_wc > 0:
            with st.expander("Additional Text Breakdown", expanded=True):
                st.write(f"**Sub-Total:** {add_dur:.1f}s")
                st.write(f"- New Counted Words: {add_wc}")
                st.caption(f"Breakdown: {', '.join(add_display_list)}")

    elif calc_btn:
        st.warning("Please enter some text to calculate.")

# --- Smart Tips Section ---
st.markdown("---")
st.subheader("Smart Optimization Tips")
tips = []
full_text = (main_text + " " + add_text)
full_text_lower = full_text.lower()

# 1. Merge Text Tip (Restored from V1.2)
if has_additional and add_wc > 0:
    # If added to main, you save the 'add_rt' (Recognition Time)
    saving = add_rt
    display_snip = add_text[:20] + "..." if len(add_text) > 20 else add_text
    tips.append(f"**Structure:** Consider merging '{display_snip}' into the main disclaimer to save **{saving:.1f}s** (Recognition Time).")

# 2. Symbol Words (Restored from V1.2)
if any(word in full_text_lower for word in SYMBOL_WORDS):
     tips.append("**Symbols:** Using symbols (£, €, %, &) instead of full words ('pounds', 'percent') does not add to the word count.")

# 3. T&Cs
if "terms and conditions" in full_text_lower:
    tips.append("**Huge Saving:** Change 'Terms and Conditions' (3 words) to 'T&Cs' (1 word). Saves 0.4s.")
elif "terms & conditions" in full_text_lower:
    tips.append("**Quick Fix:** Change 'Terms & Conditions' to 'T&Cs'. Saves 1 word (0.2s).")

# 4. "And"
if re.search(r'\band\b', full_text_lower):
    tips.append("**Space Saving:** Replace 'and' with '&' to reduce word count.")

# 5. Abbreviations
if "per annum" in full_text_lower:
    tips.append("**Quick Fix:** Change 'per annum' (2 words) to 'p.a.' (1 word). Saves 0.2s.")
if "republic of ireland" in full_text_lower:
    tips.append("**Quick Fix:** Change 'Republic of Ireland' (3 words) to 'ROI' (1 word). Saves 0.4s.")

# 6. Formatting
if any(month in full_text_lower for month in MONTHS):
    tips.append("**Formatting:** Writing dates out in full (e.g. 'January') is lengthy. Consider using numerals (e.g., '25.12.25').")
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
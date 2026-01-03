import streamlit as st
import re
from num2words import num2words

# --- Configuration ---
WORDS_TO_IGNORE_IN_NUMBERS = {"hundred", "thousand", "and"}
FRAMES_PER_SECOND = 25
MONTHS = ["january", "february", "march", "april", "may", "june",
          "july", "august", "september", "october", "november", "december"]
SYMBOL_WORDS = ["percent", "pounds", "euros"]

# --- Core Logic (Copied from V1.4) ---

def convert_number_smart(number_val):
    """
    Smart logic to handle specific number ranges for ad clearance.
    """
    # RANGE 1: 1100 - 1999 (The "Teen Hundreds" Fix)
    if 1100 <= number_val <= 1999:
        hundreds = number_val // 100
        remainder = number_val % 100
        text = f"{num2words(hundreds)} hundred"
        if remainder > 0:
            text += f" and {num2words(remainder)}"
        return text

    # RANGE 2: 2010 - 2099 (Modern Years)
    if 2010 <= number_val <= 2099:
        return num2words(number_val, to='year')

    # RANGE 3: Standard reading for everything else
    return num2words(number_val)

def get_unique_words(text):
    """Gets a list of unique, countable words, preserving order."""
    if not text:
        return []

    url_regex = r'(?:https?://)?(?:www\.)?([a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}'
    text_for_counting = re.sub(url_regex, ' websiteurl ', text)

    parts = re.split(r'(\d+)', text_for_counting)
    
    number_generated_words = []
    manual_words_in_order = []

    for part in parts:
        if part.isdigit():
            number_val = int(part)
            spoken_number = convert_number_smart(number_val)
            words_from_number = re.findall(r'\b\w+\b', spoken_number.lower())
            counted_words_from_number = [w for w in words_from_number if w not in WORDS_TO_IGNORE_IN_NUMBERS]
            number_generated_words.extend(counted_words_from_number)
        else:
            manual_words = re.findall(r'\b\w+\b', part.lower())
            manual_words_in_order.extend(manual_words)

    seen_manual_words = set()
    unique_manual_words = []
    for word in manual_words_in_order:
        if word not in seen_manual_words:
            seen_manual_words.add(word)
            unique_manual_words.append(word)
    
    return unique_manual_words + number_generated_words

def get_spoken_text(text):
    """Gets the display-friendly version of text."""
    if not text:
        return ""
    parts_for_display = re.split(r'(\d+)', text)
    spoken_phrases = []
    for part in parts_for_display:
        if part.isdigit():
            spoken_phrases.append(convert_number_smart(int(part)))
        else:
            spoken_phrases.append(part)
    return "".join(spoken_phrases)

# --- Streamlit UI ---

st.set_page_config(page_title="Clearcast Disclaimer Calculator", layout="wide")

st.title("Clearcast Disclaimer Calculator V1.4")
st.markdown("This tool calculates the duration of disclaimer text based on Clearcast/Ad guidance.")

col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("Input")
    
    main_text = st.text_area("Disclaimer Text (Main)", height=150, help="Enter the main disclaimer text here.")
    
    has_additional = st.checkbox("Include Additional/Split Text?")
    
    add_text = ""
    if has_additional:
        st.info("Enter any additional text that appears at a different time while the disclaimer is held.")
        add_text = st.text_area("Additional Text", height=100)

    # Calculate Button
    if st.button("Calculate Duration", type="primary"):
        do_calc = True
    else:
        do_calc = False

with col2:
    st.subheader("Results")

    if do_calc and (main_text or add_text):
        # --- Calculations ---
        # 1. Main Text
        main_cw = get_unique_words(main_text)
        main_wc = len(main_cw)
        main_rt = 3.0 if main_wc >= 10 else 2.0
        main_duration = (main_wc * 0.2) + main_rt if main_wc > 0 else 0
        main_st = get_spoken_text(main_text)

        # 2. Additional Text
        add_duration = 0
        add_wc = 0
        add_rt = 0
        add_st = ""
        add_cw = []
        
        if has_additional and add_text:
            add_st = get_spoken_text(add_text)
            all_add_words = get_unique_words(add_text)
            main_words_set = set(main_cw)
            # Filter words already counted in main
            add_cw = [w for w in all_add_words if w not in main_words_set]
            add_wc = len(add_cw)
            add_rt = 3.0 if add_wc >= 10 else 2.0
            add_duration = (add_wc * 0.2) + add_rt if add_wc > 0 else 0

        total_duration = main_duration + add_duration

        # --- Display Total ---
        st.metric(label="Total Duration", value=f"{total_duration:.1f}s")
        
        if total_duration > 0:
            whole_seconds = int(total_duration)
            frames = round((total_duration - whole_seconds) * FRAMES_PER_SECOND)
            st.caption(f"({whole_seconds} seconds and {frames} frames)")

        st.divider()

        # --- Breakdowns ---
        if main_wc > 0:
            with st.expander("Main Disclaimer Breakdown", expanded=True):
                st.write(f"**Sub-Total:** {main_duration:.1f}s")
                st.write(f"- Counted Words: {main_wc}")
                st.write(f"- Text Hold: {main_wc * 0.2:.1f}s")
                st.write(f"- Recognition: {main_rt:.1f}s")
                st.text(f"Interpreted As: {main_st}")
                st.caption(f"Countable Words: {', '.join(main_cw)}")

        if has_additional and add_text:
            with st.expander("Additional Text Breakdown", expanded=True):
                st.write(f"**Sub-Total:** {add_duration:.1f}s")
                st.write(f"- Counted Words: {add_wc}")
                st.write(f"- Text Hold: {add_wc * 0.2:.1f}s")
                st.write(f"- Recognition: {add_rt:.1f}s")
                st.text(f"Interpreted As: {add_st}")
                st.caption(f"Countable Words (New unique words only): {', '.join(add_cw)}")

        # --- Tips Section ---
        st.subheader("Optimization Tips")
        full_text_lower = (main_text + " " + add_text).lower()
        
        tips = []
        if has_additional and add_wc > 0:
            display_snip = add_text[:17] + "..." if len(add_text) > 20 else add_text
            tips.append(f"Consider adding '{display_snip}' to the main disclaimer to save {add_rt:.1f}s of recognition time.")
        
        if re.search(r'\band\b', full_text_lower):
            tips.append("Replace 'and' with '&' to reduce the word count.")
            
        if "terms and conditions" in full_text_lower:
            tips.append("Use 'T&Cs apply' instead of 'Terms and conditions apply' to save 2 words (0.4s).")
            
        if any(month in full_text_lower for month in MONTHS):
            tips.append("Writing dates out in full is lengthy. Consider using numerals (e.g., '25.12.25').")
            
        if "per week" in full_text_lower or "per month" in full_text_lower:
            tips.append("Use '/week' or '/month' instead of 'per week'/'per month' to save a word.")

        if tips:
            for tip in tips:
                st.warning(tip, icon="💡")
        else:
            st.success("No optimization tips found!", icon="✅")

    elif do_calc:
        st.warning("Please enter some text to calculate.")

# Footer
st.markdown("---")
st.caption("This tool is for guidance only. Always verify with Clearcast.")
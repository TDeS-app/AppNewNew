import streamlit as st
import pandas as pd
import re
from io import BytesIO
from rapidfuzz import fuzz

st.set_page_config(layout="wide")
st.title("📦 Lean Inventory Matcher for Shopify")

# ---------- Helper Functions ----------
def read_csv_files(files, label):
    dfs = []
    for file in files:
        try:
            df = pd.read_csv(file)
            dfs.append(df)
        except Exception as e:
            st.error(f"❌ Failed to read {file.name} ({label}): {e}")
    return pd.concat(dfs, ignore_index=True) if len(dfs) > 1 else dfs[0] if dfs else pd.DataFrame()

def detect_special_chars(df, label):
    special_titles = df[df['Title'].str.contains(r"[^\w\s'-]", regex=True, na=False)]['Title']
    if not special_titles.empty:
        st.warning(f"⚠️ {label} file has titles with special characters:")
        st.write(special_titles.unique().tolist())
    else:
        st.success(f"✅ No special characters found in {label} titles.")

def fuzzy_match_titles(selected_df, target_df):
    matched_rows = []
    unmatched = []
    for sel_title in selected_df['Title'].dropna().unique():
        matches = target_df[target_df['Title'].apply(lambda x: fuzz.ratio(str(x), sel_title) >= 95)]
        if matches.empty:
            unmatched.append(sel_title)
        elif len(matches) > 1:
            st.warning(f"Multiple matches found for: '{sel_title}'")
            options = matches['Title'].tolist()
            choice = st.selectbox(f"Choose a match for '{sel_title}' or skip", options + ["Skip"], key=sel_title)
            if choice != "Skip":
                matched_rows.append(matches[matches['Title'] == choice])
        else:
            matched_rows.append(matches)
    matched_df = pd.concat(matched_rows).drop_duplicates() if matched_rows else pd.DataFrame()
    return matched_df, unmatched

def match_products_by_handle(filtered_inventory_df, product_df):
    if 'Handle' in filtered_inventory_df.columns and 'Handle' in product_df.columns:
        handles = filtered_inventory_df['Handle'].unique()
        matched = product_df[product_df['Handle'].isin(handles)].drop_duplicates()
        return matched
    else:
        st.warning("⚠️ 'Handle' column not found in one of the datasets.")
        return pd.DataFrame()

# ---------- File Uploads ----------
product_files = st.file_uploader("Upload Product CSV file(s)", type="csv", accept_multiple_files=True)
inventory_files = st.file_uploader("Upload Inventory CSV file(s)", type="csv", accept_multiple_files=True)
selected_file = st.file_uploader("Upload Selected Products CSV file", type="csv")

# ---------- Preprocessing Step ----------
if product_files and inventory_files and selected_file:
    product_df = read_csv_files(product_files, "Product")
    inventory_df = read_csv_files(inventory_files, "Inventory")
    selected_df = pd.read_csv(selected_file)

    st.subheader("🔍 Special Character Scan")
    detect_special_chars(product_df, "Product")
    detect_special_chars(inventory_df, "Inventory")

    st.subheader("📊 Summary")
    st.write(f"Product rows: {len(product_df)}")
    st.write(f"Inventory rows: {len(inventory_df)}")
    st.write(f"Selected Products: {len(selected_df)}")

    if st.button("✅ Confirm & Continue"):
        # Step 2: Filter inventory using fuzzy match
        st.subheader("🔗 Matching Inventory Titles")
        filtered_inventory, unmatched_titles = fuzzy_match_titles(selected_df, inventory_df)
        if not unmatched_titles:
            st.success("✅ All selected titles matched successfully!")
        else:
            st.info(f"🔍 {len(unmatched_titles)} titles could not be matched:")
            st.write(unmatched_titles)

        st.write("### Filtered Inventory Summary")
        st.dataframe(filtered_inventory)

        # Step 3: Match products using handle
        st.subheader("🔗 Matching Products by Handle")
        filtered_products = match_products_by_handle(filtered_inventory, product_df)

        st.write("### Filtered Products Summary")
        st.dataframe(filtered_products)

        # Download buttons
        st.download_button("⬇️ Download Filtered Inventory CSV", data=filtered_inventory.to_csv(index=False).encode("utf-8"), file_name="filtered_inventory.csv", mime="text/csv")
        st.download_button("⬇️ Download Filtered Product CSV", data=filtered_products.to_csv(index=False).encode("utf-8"), file_name="filtered_products.csv", mime="text/csv")

else:
    st.info("📤 Please upload product, inventory, and selected products files to begin.")

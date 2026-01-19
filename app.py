from flask import Flask, request, render_template, send_file, session, redirect, url_for

from datetime import timedelta
import secrets

import pandas as pd
import numpy as np

import re

import os
import io

from werkzeug.utils import secure_filename

app = Flask(__name__)

# In-memory store for demo purposes (resets on restart)
DATA_STORE = {}
MAX_STORE_ITEMS = 50

app.secret_key = secrets.token_hex(16)
app.permanent_session_lifetime = timedelta(minutes=30)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route('/')
def home():
    return render_template("index.html")

@app.route('/about')
def about():
    return render_template("about.html")

@app.route("/clean", methods=["GET", "POST"])
def clean():
    # --------------------------
    # Defaults so template never breaks
    # --------------------------
    alert = ""
    df_info = []
    df_head = ""
    df_duplicates = ""
    df_describe = ""
    df_duplicates_deleted = ""
    df_missings = {}

    # numeric lists for UI
    numeric_cols_list = []
    date_cols_list = []

    # numeric-clean outputs
    df_describe_4 = ""
    df_describe_2 = ""
    missings_percentage = {}
    columns_less_5_perc_missing = []
    missings_percentage_after = {}
    fill_cat_mis_val = False
    missings_percentage_after2 = {}
    is_missings_percentage_after2_string = False
    replace_numeric_nan = False
    numeric_cols_cleaned = []

    # date-clean outputs
    df_describe_3 = ""
    df_describe_5 = ""
    df_info_2 = []
    df_head_5 = ""
    df_tail_5 = ""
    date_col = ""
    replace_date_nan = False

    # --------------------------
    # POST: upload a dataset
    # --------------------------
    if request.method == "POST":
        file = request.files.get("file")
        if not file:
            session["flash"] = "No file selected"
            return redirect(url_for("clean"))

        filename = secure_filename(file.filename)
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)

        df = pd.read_csv(filepath)

        # standardize columns + string values
        df.columns = df.columns.str.strip().str.lower().str.replace(r"\s+", " ", regex=True)
        for col in df.select_dtypes(include=["object"]).columns:
            df[col] = df[col].astype(str).str.strip().str.lower()

        # dataset_id ONCE
        dataset_id = secrets.token_urlsafe(16)
        session["dataset_id"] = dataset_id
        session.permanent = True

        # info
        buffer = io.StringIO()
        df.info(buf=buffer)
        df_info = buffer.getvalue().split("\n")

        # head
        df_head = df.head().to_html(classes="table table-striped", escape=False)

        # duplicates
        duplicates_count = df.duplicated().sum()
        if duplicates_count == 0:
            df_duplicates = "There are no duplicated rows in the dataset"
            df_duplicates_deleted = f"There were {duplicates_count} duplicates in the '{filename}' dataset"
        else:
            df_duplicates = f"Number of duplicated rows: {duplicates_count}"
            df.drop_duplicates(inplace=True)
            df_duplicates_deleted = f"Dataset {duplicates_count} duplicated rows have been dropped"

        # missing values (dict)
        if df.isnull().sum().sum() == 0:
            df_missings = {}
        else:
            df_missings = df.isnull().sum().to_dict()

        # summary
        df_describe = df.describe(include="all").to_html(classes="table table-striped", escape=False)

        # detect numeric-like columns
        numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
        for col in df.columns:
            if col in numeric_cols:
                continue
            if "id" in col.lower():
                continue
            if df[col].dtype == "object":
                sample = df[col].dropna().astype(str).str.strip().head(50)
                cleaned = sample.str.replace(r"[^\d\.\-]", "", regex=True)
                parsed = pd.to_numeric(cleaned, errors="coerce")
                if len(parsed) > 0:
                    ratio = parsed.notna().mean()
                    avg_len = cleaned.replace("", pd.NA).dropna().str.len().mean()
                    if ratio >= 0.7 and (avg_len is None or avg_len <= 10):
                        numeric_cols.append(col)

        # detect date-like columns
        date_cols = []
        for col in df.columns:
            if str(df[col].dtype).startswith("datetime"):
                date_cols.append(col)
                continue
            if df[col].dtype == "object":
                sample = df[col].dropna().astype(str).head(30)
                if len(sample) > 0:
                    parsed = pd.to_datetime(sample, errors="coerce")
                    if parsed.notna().mean() >= 0.8:
                        date_cols.append(col)

        # save base CSV + ALL upload outputs for later GET requests
        DATA_STORE[dataset_id] = {
            "csv": df.to_csv(index=False),
            "numeric_cols": numeric_cols,
            "date_cols": date_cols,
            "columns": df.columns.tolist(),
            "df_missings": df_missings,
            "original_filename": filename,

            # ✅ store upload outputs so they stay visible after redirects
            "df_info": df_info,
            "df_head": df_head,
            "df_duplicates": df_duplicates,
            "df_describe": df_describe,
            "df_duplicates_deleted": df_duplicates_deleted,

            "flash": f"File {filename} uploaded successfully! Loaded {df.shape[0]} rows",
        }

        # Optional cap
        if len(DATA_STORE) > MAX_STORE_ITEMS:
            DATA_STORE.pop(next(iter(DATA_STORE)))

        return redirect(url_for("clean"))

    # --------------------------
    # GET: load state from DATA_STORE (after redirects)
    # --------------------------
    dataset_id = session.get("dataset_id")
    flash_msg = session.pop("flash", "")

    if dataset_id and dataset_id in DATA_STORE:
        flash_msg = DATA_STORE[dataset_id].pop("flash", flash_msg)

        numeric_cols_list = DATA_STORE[dataset_id].get("numeric_cols", [])
        date_cols_list = DATA_STORE[dataset_id].get("date_cols", [])
        df_missings = DATA_STORE[dataset_id].get("df_missings", {})

        # ✅ load upload outputs back
        df_info = DATA_STORE[dataset_id].get("df_info", [])
        df_head = DATA_STORE[dataset_id].get("df_head", "")
        df_duplicates = DATA_STORE[dataset_id].get("df_duplicates", "")
        df_describe = DATA_STORE[dataset_id].get("df_describe", "")
        df_duplicates_deleted = DATA_STORE[dataset_id].get("df_duplicates_deleted", "")

        # numeric-clean outputs
        df_describe_4 = DATA_STORE[dataset_id].get("df_describe_4", "")
        df_describe_2 = DATA_STORE[dataset_id].get("df_describe_2", "")
        missings_percentage = DATA_STORE[dataset_id].get("missings_percentage", {})
        columns_less_5_perc_missing = DATA_STORE[dataset_id].get("columns_less_5_perc_missing", [])
        missings_percentage_after = DATA_STORE[dataset_id].get("missings_percentage_after", {})
        fill_cat_mis_val = DATA_STORE[dataset_id].get("fill_cat_mis_val", False)
        missings_percentage_after2 = DATA_STORE[dataset_id].get("missings_percentage_after2", {})
        is_missings_percentage_after2_string = DATA_STORE[dataset_id].get("is_missings_percentage_after2_string", False)
        replace_numeric_nan = DATA_STORE[dataset_id].get("replace_numeric_nan", False)
        numeric_cols_cleaned = DATA_STORE[dataset_id].get("numeric_cols_cleaned", [])

        # date-clean outputs
        df_describe_3 = DATA_STORE[dataset_id].get("df_describe_3", "")
        df_describe_5 = DATA_STORE[dataset_id].get("df_describe_5", "")
        df_info_2 = DATA_STORE[dataset_id].get("df_info_2", [])
        df_head_5 = DATA_STORE[dataset_id].get("df_head_5", "")
        df_tail_5 = DATA_STORE[dataset_id].get("df_tail_5", "")
        date_col = DATA_STORE[dataset_id].get("date_col_selected", "")
        replace_date_nan = DATA_STORE[dataset_id].get("replace_date_nan", False)

    return render_template(
        "clean.html",
        alert=flash_msg or alert,

        # upload outputs
        df_info=df_info,
        df_head=df_head,
        df_duplicates=df_duplicates,
        df_describe=df_describe,
        df_duplicates_deleted=df_duplicates_deleted,
        df_missings=df_missings,

        # UI column detection
        numeric_cols_list=numeric_cols_list,
        date_cols_list=date_cols_list,

        # numeric-clean outputs
        replace_numeric_nan=replace_numeric_nan,
        numeric_cols=numeric_cols_cleaned,
        df_describe_4=df_describe_4,
        df_describe_2=df_describe_2,
        missings_percentage=missings_percentage,
        columns_less_5_perc_missing=columns_less_5_perc_missing,
        missings_percentage_after=missings_percentage_after,
        fill_cat_mis_val=fill_cat_mis_val,
        missings_percentage_after2=missings_percentage_after2,
        is_missings_percentage_after2_string=is_missings_percentage_after2_string,

        # date-clean outputs
        date_col=date_col,
        replace_date_nan=replace_date_nan,
        df_describe_3=df_describe_3,
        df_describe_5=df_describe_5,
        df_info_2=df_info_2,
        df_head_5=df_head_5,
        df_tail_5=df_tail_5,
    )
   
@app.route("/clean_numeric_columns", methods=["POST"])
def clean_numeric_columns():
    # get user input
    numeric_cols_input = request.form.get("numeric_cols")
    if not numeric_cols_input:
        session["flash"] = "No numeric column names provided"
        return redirect(url_for("clean") + "#numeric-clean")

    # load dataset from server-side store
    dataset_id = session.get("dataset_id")
    if not dataset_id or dataset_id not in DATA_STORE:
        print("DEBUG dataset_id from session:", dataset_id)
        print("DEBUG keys in DATA_STORE:", list(DATA_STORE.keys()))
        return "Error: No dataset found. Please upload a file first.", 400

    df = pd.read_csv(io.StringIO(DATA_STORE[dataset_id]["csv"]))

    # convert user input string to list
    list_attr_to_numeric = [
        re.sub(r"\s+", " ", col.strip().lower())
        for col in numeric_cols_input.split(",")
    ]

    # validate column names
    existing_numeric_cols = [col for col in list_attr_to_numeric if col in df.columns]
    if not existing_numeric_cols:
        DATA_STORE[dataset_id]["flash"] = (
            "None of the provided columns exist in the dataset. "
            f"Available columns: {', '.join(df.columns)}"
        )
        DATA_STORE[dataset_id]["replace_numeric_nan"] = False
        DATA_STORE[dataset_id]["numeric_cols_cleaned"] = []
        return redirect(url_for("clean") + "#numeric-clean")

    # convert selected columns to numeric
    for col in existing_numeric_cols:
        df[col] = df[col].astype(str).str.replace(r"[^\d.]", "", regex=True)
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # ---- compute outputs ----
    df_describe_4 = df.describe(include="all").to_html(classes="table table-striped", escape=False)

    missings_percentage = (df.isnull().sum() / len(df)) * 100
    missings_percentage = missings_percentage.loc[missings_percentage > 0]
    columns_less_5_perc_missing = missings_percentage.loc[missings_percentage < 5].index.tolist()
    missings_percentage = missings_percentage.to_dict()

    df.dropna(subset=columns_less_5_perc_missing, inplace=True)

    missings_percentage_after = (df.isnull().sum() / len(df)) * 100
    missings_percentage_after = missings_percentage_after.loc[missings_percentage_after > 0].to_dict()

    df.fillna(df.mode().iloc[0], inplace=True)

    missings_percentage_after2 = (df.isnull().sum() / len(df)) * 100
    missings_percentage_after2 = missings_percentage_after2.loc[missings_percentage_after2 > 0].to_dict()

    if not missings_percentage_after2:
        missings_percentage_after2 = "There are no missing values left"
        is_missings_percentage_after2_string = True
    else:
        is_missings_percentage_after2_string = False

    df_describe_2 = df.describe(include="all").to_html(classes="table table-striped", escape=False)

    # ---- save back into SAME dataset_id ----
    DATA_STORE[dataset_id]["csv"] = df.to_csv(index=False)

    DATA_STORE[dataset_id]["flash"] = (
        f"Numeric columns cleaned: {', '.join(existing_numeric_cols)}. "
        "Invalid values replaced with NaN."
    )

    DATA_STORE[dataset_id]["df_describe_4"] = df_describe_4
    DATA_STORE[dataset_id]["df_describe_2"] = df_describe_2
    DATA_STORE[dataset_id]["missings_percentage"] = missings_percentage
    DATA_STORE[dataset_id]["columns_less_5_perc_missing"] = columns_less_5_perc_missing
    DATA_STORE[dataset_id]["missings_percentage_after"] = missings_percentage_after
    DATA_STORE[dataset_id]["fill_cat_mis_val"] = True
    DATA_STORE[dataset_id]["missings_percentage_after2"] = missings_percentage_after2
    DATA_STORE[dataset_id]["is_missings_percentage_after2_string"] = is_missings_percentage_after2_string
    DATA_STORE[dataset_id]["replace_numeric_nan"] = True
    DATA_STORE[dataset_id]["numeric_cols_cleaned"] = existing_numeric_cols

    # IMPORTANT: do NOT touch numeric_cols / date_cols
    return redirect(url_for("clean") + "#numeric-clean")

@app.route("/clean_date_column", methods=["POST"])
def clean_date_column():
    # get user input, normalize to match your standardized column names
    date_col = re.sub(r"\s+", " ", request.form.get("date_col", "").strip().lower())

    if not date_col:
        session["flash"] = "Please enter a date column name."
        return redirect(url_for("clean") + "#date-clean")

    # load the cleaned dataset
    dataset_id = session.get("dataset_id")
    if not dataset_id or dataset_id not in DATA_STORE:
        print("DEBUG dataset_id from session:", dataset_id)
        print("DEBUG keys in DATA_STORE:", list(DATA_STORE.keys()))
        return "Error: No dataset found. Please upload a file first.", 400

    df = pd.read_csv(io.StringIO(DATA_STORE[dataset_id]["csv"]))

    # Check if the column exists in the dataset
    if date_col not in df.columns:
        DATA_STORE[dataset_id]["flash"] = (
            f"Error: The column '{date_col}' does not exist. "
            f"Available columns: {', '.join(df.columns)}"
        )
        return redirect(url_for("clean") + "#date-clean")

    # define a regex pattern for valid date formats
    date_pattern = r"(\d{4}-\d{2}-\d{2})|(\d{2}/\d{2}/\d{4})|(\d{2}-\d{2}-\d{4})"

    # invalid values (not matching a date-ish pattern)
    invalid_values = df[~df[date_col].astype(str).str.match(date_pattern, na=False)][date_col].unique()

    # replace invalid values with NA, then convert
    df[date_col] = df[date_col].replace(invalid_values, pd.NA, regex=True)
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")

    # fill invalid/missing dates with default
    df[date_col] = df[date_col].fillna(pd.to_datetime("2000-01-01"))

    # flag + message
    DATA_STORE[dataset_id]["replace_date_nan"] = True
    DATA_STORE[dataset_id]["flash"] = f"Date column cleaned: {date_col}. Invalid dates replaced."

    # summary statistics (after date cleaning, before encoding)
    df_describe_3 = df.describe(include="all").to_html(classes="table table-striped", escape=False)

    # categorical columns (object type)
    categorical_columns = df.select_dtypes(include=["object"]).columns.tolist()

    # drop columns with all-unique values
    unique_value_columns = [col for col in categorical_columns if df[col].is_unique]
    df.drop(columns=unique_value_columns, inplace=True, errors="ignore")

    # update categorical columns after dropping
    categorical_columns = df.select_dtypes(include=["object"]).columns.tolist()

    # encode categoricals
    df = pd.get_dummies(df, columns=categorical_columns)

    # Convert True/False to 1/0
    bool_cols = df.select_dtypes(include="bool").columns
    if len(bool_cols) > 0:
        df[bool_cols] = df[bool_cols].astype(int)

    # also handle string "true"/"false" just in case
    df = df.replace({"true": 1, "false": 0, True: 1, False: 0})

    # save cleaned CSV back (same dataset_id)
    DATA_STORE[dataset_id]["csv"] = df.to_csv(index=False)

    # outputs for UI
    DATA_STORE[dataset_id]["df_describe_3"] = df_describe_3
    DATA_STORE[dataset_id]["df_describe_5"] = df.describe(include="all").to_html(classes="table table-striped", escape=False)

    buffer = io.StringIO()
    df.info(buf=buffer)
    DATA_STORE[dataset_id]["df_info_2"] = buffer.getvalue().split("\n")

    DATA_STORE[dataset_id]["df_head_5"] = df.head().to_html(classes="table table-striped", escape=False)
    DATA_STORE[dataset_id]["df_tail_5"] = df.tail().to_html(classes="table table-striped", escape=False)

    DATA_STORE[dataset_id]["date_col_selected"] = date_col

    # Optional: hide date-clean form after you already cleaned the date column
    DATA_STORE[dataset_id]["date_cols"] = []

    return redirect(url_for("clean") + "#date-clean")


@app.route("/download_cleaned_data")
def download_cleaned_data():
    dataset_id = session.get("dataset_id")

    # If dataset doesn't exist, STOP and return an error response
    if not dataset_id or dataset_id not in DATA_STORE:
        print("DEBUG dataset_id from session:", dataset_id)
        print("DEBUG keys in DATA_STORE:", list(DATA_STORE.keys()))
        return "Error: No cleaned dataset found. Please upload a file first.", 400

    return send_file(
        io.BytesIO(DATA_STORE[dataset_id]["csv"].encode("utf-8")),
        mimetype="text/csv",
        as_attachment=True,
        download_name=f"cleaned_{DATA_STORE[dataset_id].get('original_filename', 'data')}.csv",
    )

@app.route('/contact')
def contact():
    email = "shap0011@algonquinlive.com"
    tel = "613-123-1234"
    return render_template("contact.html", email=email, tel=tel)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)

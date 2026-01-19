from flask import Flask, request, render_template, send_file

import pandas as pd
import numpy as np

import re

import os
import io

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"

@app.route('/')
def home():
    return render_template("index.html")

@app.route('/about')
def about():
    return render_template("about.html")

@app.route('/clean', methods=["GET", "POST"])
def clean():
    alert = ""
    df_info = [] 
    df_head = ""
    duplicates_count = 0
    df_duplicates = ""
    df_describe = ""
    df_duplicates_deleted = ""

    if request.method == "POST":
        file = request.files.get("file") # get file

        # add exception handling, file must be only CSV -- TODO for later
        if not file:
            alert = "No file selected"
        else:
            filepath = os.path.join(UPLOAD_FOLDER, file.filename)
            file.save(filepath)

            df = pd.read_csv(filepath)

            # define cleaned_filepath
            cleaned_filepath = os.path.join(UPLOAD_FOLDER, "cleaned_data.csv")
        
            
            alert = f"File {file.filename} uploaded successfully! Loaded {df.shape[0]} rows"

            
            # standardize dataset column names (strip spaces, lowercase, remove extra spaces inside names)
            df.columns = df.columns.str.strip().str.lower().str.replace(r"\s+", " ", regex=True)

            # standardize dataset values (strip spaces, lowercase)
            for col in df.select_dtypes(include=["object"]).columns:
                df[col] = df[col].str.strip().str.lower()

            # info
            buffer = io.StringIO()
            df.info(buf=buffer)
            df_info = buffer.getvalue().split("\n") 

            # head
            df_head = df.head().to_html(classes="table table-striped", escape=False)

            duplicates_count = df.duplicated().sum()
            # duplicates
            if duplicates_count == 0: 
                df_duplicates = "There are no duplicated rows in the dataset"
            else:
                df_duplicates = f"Number of duplicated rows: {duplicates_count}"

            # missing values
            if df.isnull().sum().sum() == 0: 
                df_missings = "There is no missing values in the dataset"
            else:
                df_missings = f"Number of missing values per column:\n{df.isnull().sum()}"

            # summary statistics
            df_describe = df.describe(include="all").to_html(classes="table table-striped", escape=False)

            # drop duplicates
            if duplicates_count == 0: 
                df_duplicates_deleted = f"There were {duplicates_count} duplicates in the '{file.filename}' dataset"
                # pass
            else:
                df.drop_duplicates(inplace=True)
                df_duplicates_deleted = f"Dataset {duplicates_count} duplicated rows have been droppedDeletinf" 

            # save the cleaned dataset
            df.to_csv(cleaned_filepath, index=False)


    return render_template(
        "clean.html", 
        alert=alert, 
        df_info=df_info, 
        df_head=df_head, 
        df_duplicates=df_duplicates, 
        df_describe=df_describe, 
        df_duplicates_deleted=df_duplicates_deleted       
    )

@app.route('/clean_numeric_columns', methods=["POST"])
def clean_numeric_columns():
    replace_numeric_nan = False
    df_describe_4 = ""

    df_missings = ""  
    missings_percentage = {}
    columns_less_5_perc_missing = []
    missings_percentage_after = {}  
    fill_cat_mis_val = False
    missings_percentage_after2 = {}
    is_missings_percentage_after2_string = False
    df_describe_2 = ""

    # get user input
    numeric_cols_input = request.form.get("numeric_cols")

    if not numeric_cols_input:
        alert = "No numeric column names provided"
        return render_template("clean.html", alert=alert)

    # convert user input string to a list, remove extra spaces
    list_attr_to_numeric = [col.strip().lower() for col in numeric_cols_input.split(",")]

    # load the cleaned dataset
    cleaned_filepath = os.path.join(UPLOAD_FOLDER, "cleaned_data.csv")

    if not os.path.exists(cleaned_filepath):
        return "Error: No dataset found. Please upload a file first.", 400

    df = pd.read_csv(cleaned_filepath)

    # validate column names, keep only names which present in the dataset
    existing_numeric_cols = [re.sub(r"\s+", " ", col.strip().lower()) for col in list_attr_to_numeric if re.sub(r"\s+", " ", col.strip().lower()) in df.columns]

    if not existing_numeric_cols:
        alert = f"None of the provided columns exists in the dataset. Available columns: {', '.join(df.columns)}"
        return render_template("clean.html", alert=alert)

    # convert data type of selected columns to numeric format
    for col in existing_numeric_cols:
        df[col] = df[col].astype(str).str.replace(r"[^\d.]", "", regex=True)  # keep only numbers & decimal points
        df[col] = pd.to_numeric(df[col], errors="coerce")  # convert to numeric (invalid values -> NaN)

    # save the cleaned dataset
    df.to_csv(cleaned_filepath, index=False)

    # set flag to True
    replace_numeric_nan = True
    alert = f"Numeric columns cleaned: {', '.join(existing_numeric_cols)}. Invalid values replaced with NaN."

    # summary statistics
    df_describe_4 = df.describe(include="all").to_html(classes="table table-striped", escape=False)

    ##########################

    # missings percentage
    missings_percentage = (df.isnull().sum() / len(df)) * 100
    missings_percentage = missings_percentage.loc[missings_percentage > 0] # Show only columns with missing values

    # identify columns with less than 5% missing values
    columns_less_5_perc_missing = missings_percentage.loc[missings_percentage < 5].index.tolist() # get the column name dynamically

    # convert to dictionary
    missings_percentage = missings_percentage.to_dict()

    # drop records with missing values where columns have less than 5% missing values
    df.dropna(subset=columns_less_5_perc_missing, inplace=True)

    # check again the percentage of missing values
    missings_percentage_after = (df.isnull().sum() / len(df)) * 100
    missings_percentage_after = missings_percentage_after.loc[missings_percentage_after > 0] # Show only columns with missing values

    # convert to dictionary
    missings_percentage_after = missings_percentage_after.to_dict()

    # fill categorical missing values with the most frequent category
    df.fillna(df.mode().iloc[0], inplace=True)

    # save/update the 'cleaned_data.csv' dataset ()
    df.to_csv(cleaned_filepath, index=False)

    # set flag to True
    fill_cat_mis_val = True

    # check again the percentage of missing values
    missings_percentage_after2 = (df.isnull().sum() / len(df)) * 100
    missings_percentage_after2 = missings_percentage_after2.loc[missings_percentage_after2 > 0] # Show only columns with missing values

    # convert to dictionary
    missings_percentage_after2 = missings_percentage_after2.to_dict()

    if not missings_percentage_after2:
       missings_percentage_after2 = "There are no missing values left"
       is_missings_percentage_after2_string = True 
    else:
       is_missings_percentage_after2_string = False 


    # summary statistics
    df_describe_2 = df.describe(include="all").to_html(classes="table table-striped", escape=False)


    return render_template(
        "clean.html", 
        alert=alert, 
        numeric_cols=existing_numeric_cols,
        replace_numeric_nan=replace_numeric_nan,
        df_describe_4=df_describe_4,
              
        df_missings=df_missings,    
        missings_percentage=missings_percentage,
        columns_less_5_perc_missing=columns_less_5_perc_missing,
        missings_percentage_after=missings_percentage_after,
        fill_cat_mis_val=fill_cat_mis_val,
        missings_percentage_after2=missings_percentage_after2,
        is_missings_percentage_after2_string=is_missings_percentage_after2_string,
        df_describe_2=df_describe_2 
    )

@app.route('/clean_date_column', methods=["POST"])
def clean_date_column():
    replace_date_nan = False
    df_describe_3 = ""
    categorical_columns = []
    categorical_values = {}
    df_describe_5 = ""
    df_info_2 = [] 
    df_head_5 = ""
    df_tail_5 = ""

    # get user input, strip spaces
    date_col = request.form.get("date_col", "").strip()

    # load the cleaned dataset
    cleaned_filepath = os.path.join(UPLOAD_FOLDER, "cleaned_data.csv")

    # if no file uploaded
    if not os.path.exists(cleaned_filepath):
        return "Error: No dataset found. Please upload a file first.", 400

    # save the data in 'cleaned_data.csv'
    df = pd.read_csv(cleaned_filepath)

    # Check if the column exists in the dataset
    if date_col not in df.columns:
        alert = f"Error: The column '{date_col}' does not exist in the dataset. Available columns: {', '.join(df.columns)}"
        return render_template("clean.html", alert=alert)
    
    # define a regex pattern for valid date formats
    date_pattern =  r"(\d{4}-\d{2}-\d{2})|(\d{2}/\d{2}/\d{4})|(\d{2}-\d{2}-\d{4})"
    
    # find rows where the 'Transaction Date' column's value does not match a valid date format
    invalid_values = df[~df[date_col].astype(str).str.match(date_pattern, na=False)][date_col].unique()

    # replace all invalid values with NaN
    df[date_col] = df[date_col].replace(invalid_values, pd.NA, regex=True)

    # convert to datetime, forcing invalid dates to NaT
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce") # not displaying NaT correctly, shows as NaN

    # replace NaN with a default date '2000-01-01'
    df[date_col] = df[date_col].fillna(pd.to_datetime('2000-01-01'))

    # save cleaned dataset
    df.to_csv(cleaned_filepath, index=False)

    # set flag to True
    replace_date_nan = True
    alert = f"Date column selected: {date_col}. Invalid dates replaced."

    # summary statistics
    df_describe_3 = df.describe(include="all").to_html(classes="table table-striped", escape=False)

    # columns with object data type
    categorical_columns = df.select_dtypes(include=['object']).columns.tolist()

    # find columns with all unique values
    unique_value_columns = [col for col in categorical_columns if df[col].is_unique]  

    # drop the unique value columns
    df.drop(columns=unique_value_columns, inplace=True)

    # update categorical_columns
    categorical_columns = df.select_dtypes(include=['object']).columns.tolist()
    
    # unique values for each categorical column
    for col in categorical_columns:
        categorical_values[col] = df[col].unique().tolist()

    # convert categorical data into numerical formats
    df = pd.get_dummies(df, columns=categorical_columns)
    
    # save cleaned dataset
    df.to_csv(cleaned_filepath, index=False)

    # summary statistics
    df_describe_5 = df.describe(include="all").to_html(classes="table table-striped", escape=False)

    # info
    buffer = io.StringIO()
    df.info(buf=buffer)
    df_info_2 = buffer.getvalue().split("\n") 

    # head & tail
    df_head_5 = df.head().to_html(classes="table table-striped", escape=False)
    df_tail_5 = df.tail().to_html(classes="table table-striped", escape=False)
    
    return render_template(
        "clean.html", 
        alert=alert, 
        date_col=date_col,
        replace_date_nan=replace_date_nan,
        df_describe_3=df_describe_3,
        categorical_columns=categorical_columns,
        categorical_values=categorical_values,
        df_describe_5=df_describe_5,
        df_info_2=df_info_2,
        df_head_5=df_head_5,
        df_tail_5=df_tail_5
    )

@app.route('/download_cleaned_data')
def download_cleaned_data():
    cleaned_filepath = os.path.join(UPLOAD_FOLDER, "cleaned_data.csv")

    if not os.path.exists(cleaned_filepath):
        return "Error: No cleaned dataset found.", 400

    return send_file(cleaned_filepath, as_attachment=True, download_name="cleaned_data.csv")

@app.route('/contact')
def contact():
    email = "shap0011@algonquinlive.com"
    tel = "613-123-1234"
    return render_template("contact.html", email=email, tel=tel)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)

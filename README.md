# OHA Decision Database Scraping Scripts

Python scripts that export public U.S. Department of Education Office of Hearings and Appeals (OHA) decision listings to CSV files for review, analysis, and preparation for Salesforce imports.

                              /\            
                  ___________/  \___________
                 /       THE WEB ARCHIVE    \
                /____________________________\
          .--------||-------||-------||--------.
         /         ||       ||       ||         \
        /    .oooo.    ooo   ooo       .o.        \
       |    d8P  Y8b   888   888      .888.        |
       |   888    888  888ooo888     .8"888.       |
       |   888    888  888   888    .8' `888.      |
       |   `88b  d88'  888   888   .88ooo8888.     |
       |    `Y88P'    o888o o888o o88'     `888o   |
        \                                          /
         '----------------------------------------'
              ||   _____  ||  _____   ||
              ||  /____/| || /____/|  ||
              ||  | PDF | || | PDF |  ||
              ||  |____|/ || |____|/  ||
          ____||__________||__________||____
         /__________________________________\
                         |       .----------.
                  \  \   |   /  /|  .CSV    |
                   \  .--'--.  / |----------|
                -----( o  o )----|  [] []   |
                   / /`----'\ \  |  [] []   |
                  / /        \ \ '----------'

## Overview

The Department of Education publishes searchable tables of administrative decisions. Each table contains identifying information, such as a docket number and a respondent or recipient, plus a link to a decision document.

These scripts automate the process of collecting those table entries. Instead of manually copying records from each page, a script opens the website in Google Chrome, retrieves the table's rows through its DataTables interface, and writes the results to a CSV file.

**The scripts collect listing metadata and document URLs. They do not download or extract PDFs.**

## Supported Databases

| Database | Exported columns | Output file |
| --- | --- | --- |
| [OHA Judges' Decisions](https://www.ed.gov/laws-and-policy/hearings-and-appeals/oha-judges-decisions-database) | Docket Number, Respondent, View Decision | `oha_judges_decisions.csv` |
| [Secretary Decisions](https://www.ed.gov/laws-and-policy/hearings-and-appeals/hearings-and-appeals-secretary-decisions) | Year, Docket Number, Recipient, Topic, Date, View Document | `oha_secretary_decisions.csv` |
| [Salary Overpayments: Waiver and Offset Decisions](https://www.ed.gov/about/doing-business-ed/working-ed/onboarding-documents/salary-overpayment-matters-ed/salary-overpayments-waiver-and-offset-decisions) | Year, Docket Number, Respondent, View Decision | `oha_salary_overpayment_decisions.csv` |

Record counts change as the Department updates its databases. Script does not rely on a fixed db size. 


## Installation

The commands below use **Windows PowerShell**.

### 1. Open the project folder

Download or clone this repository, then open the folder containing the Python scripts in Visual Studio Code.

Open IDE terminal and move to the repo. 

### 2. Confirm Python is installed

Run:

```powershell
python --version
python -m pip --version
```

Both commands should display a version number. If either command fails, install or repair Python and pip, then reload your IDE.

**NOTE:** Google Chrome must also be installed for Selenium to interact with webpages. 

### 3. Install the dependencies

Run:

```powershell
python -m pip install selenium beautifulsoup4
```

This installs:

- **Selenium:** Opens Chrome and retrieves the website's table data.
- **Beautiful Soup:** Parses the table HTML to extract field values and document links.

A virtual environment is not required.

### 4. Run a script

From the folder containing your script, run:

```powershell
python .\<script-name>.py
```

Replace `<script-name>.py` with the actual scrape file. The filenames indicate which OHA db each script targets.  

**NOTE:** Leave the automated Chrome window open while the script runs. When collection finishes successfully, the script saves the CSV beside the Python script and closes Chrome.


## Running a Scraper

### 1. Select the correct script

Open the script and check its `PAGE_URL` and `OUTPUT_PATH` constants to confirm which database it targets.

**Filename convention:** The examples below assume that the three script versions have been saved separately using these suggested names. If your files have different names, substitute the actual filenames.

| Suggested script filename | Database |
| --- | --- |
| `scrape_oha_judges.py` | Judges' decisions |
| `scrape_oha_secretary.py` | Secretary decisions |
| `scrape_oha_salary_overpayments.py` | Salary overpayment decisions |

### 2. Run the selected script

Run one command at a time:

```powershell
.\.venv\Scripts\python.exe .\scrape_oha_judges.py
```

```powershell
.\.venv\Scripts\python.exe .\scrape_oha_secretary.py
```

```powershell
.\.venv\Scripts\python.exe .\scrape_oha_salary_overpayments.py
```

### 3. Leave the browser open

Chrome opens visibly while the script runs. Do not close the automated window or change its filters during collection. The script closes the browser when it finishes.

On the first run, Selenium may need additional time to obtain a compatible driver. The table wait itself is configured for up to 60 seconds after navigation.

### 4. Confirm success

A successful run prints:

- The source page title and URL.
- The website's reported record count.
- The extracted record count.
- A success message and the output file path.

**Only treat the export as complete when the script reports success and the counts match. Confirm the number of rows matches what is listed on the OHA website's for each database.** 

## How Collection Works

1. Selenium opens the configured source page in Chrome.
2. The script waits for the relevant DataTables instance to initialize.
3. It clears DataTables search filters and requests all rows rather than relying on pagination buttons.
4. It obtains the row HTML from the client-side table.
5. Beautiful Soup extracts the fields and resolves document links to absolute URLs.
6. The script compares the number of extracted rows with the table's reported total.
7. It writes a CSV only after the count check passes.

The scripts preserve source rows rather than deduplicating by docket number. Multiple decisions may relate to the same docket. These should be preserved when importing data to Salesforce. 

## Output and Validation

Exports are saved beside the script, not necessarily in the terminal's current working directory.

- CSV encoding is **UTF-8 with a byte-order mark** (`utf-8-sig`).
- Document columns contain hyperlinks as URL strings, not PDF file contents.
- Secretary decision dates retain the source site's displayed formatting.
- Blank source values remain blank and are reported for review where the script provides a `REVIEW` message.
- Rows with multiple different document links cause the script to stop rather than silently discard a document.
- Successful reruns replace the corresponding output file. Back up any export you need to retain.

Before using an export:

1. Confirm the success message and matching row counts.
2. Review any `REVIEW` messages.
3. Open the CSV in a spreadsheet application or text editor.
4. Compare several entries with the source website.
5. Open several document URLs to verify their destinations.
6. Check repeated docket numbers before selecting a Salesforce matching key.

**Matching counts verify row coverage against the loaded table, not the accuracy of the underlying government records or the availability of every linked PDF.**

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| `ModuleNotFoundError` for `selenium` or `bs4` | Install both dependencies by running `python -m pip install selenium beautifulsoup4`. Make sure you use the same `python` command to install the packages and run the script. |
| Chrome does not start or the driver cannot be obtained | Confirm that Google Chrome is installed. Also check your network connection, proxy settings, organizational restrictions, and Selenium driver errors. |
| `InvalidSessionIdException` | The browser session ended before the script finished. Run the script again and do not close the automated Chrome window. If Chrome closes on its own, investigate the browser or driver failure. |
| Timeout waiting for the table | Review the saved `page.html` and `page.png` files. The page may be loading slowly, blocking automated access, using a changed table structure, or failing to initialize its DataTables component. |
| Only 10 rows appear in an export | Confirm that the script retrieves all rows through the DataTables interface rather than scraping only the first visible page. |
| Count mismatch | Do not remove or bypass the count check. Compare the website's reported total with the extracted rows, then review the table structure and extraction logic for skipped or unexpected records. |
| Server-side pagination error | The current scraper cannot retrieve all rows from a server-side table. That database requires a separate pagination or data-endpoint implementation. |
| Permission error when writing the CSV | Close the CSV in Microsoft Excel or another application. Confirm that you have permission to write files to the script's folder. |
| A CSV exists after a failed run | The file may be from an earlier successful run. Check the console output and the CSV's modification time before treating it as the latest export. |
| Salesforce import fails | Review the CSV mappings, required fields, date formats, lookup or master-detail relationships, duplicate rules, validation rules, and Apex trigger errors. |

When scraping fails, the script attempts to save `page.html` and `page.png` in a database-specific debug folder. These files show the page content and browser state at the time of the failure.

Diagnostic capture may also fail if Chrome closes or the Selenium session ends before the files can be saved.


## Responsible Use and Data Handling

Only use this script on the OHA website on public db's. Don't do anything silly. 

## References

- [OHA Judges' Decisions Database](https://www.ed.gov/laws-and-policy/hearings-and-appeals/oha-judges-decisions-database)
- [Hearings and Appeals: Secretary Decisions](https://www.ed.gov/laws-and-policy/hearings-and-appeals/hearings-and-appeals-secretary-decisions)
- [Salary Overpayments: Waiver and Offset Decisions](https://www.ed.gov/about/doing-business-ed/working-ed/onboarding-documents/salary-overpayment-matters-ed/salary-overpayments-waiver-and-offset-decisions)
- [Selenium Manager documentation](https://www.selenium.dev/documentation/selenium_manager/)
- [How to Write a Clean, Professional README.md: A Practical Guide for Developers](https://dev.to/kailashnirmal/how-to-write-a-clean-professional-readmemd-a-practical-guide-for-developers-2o47)


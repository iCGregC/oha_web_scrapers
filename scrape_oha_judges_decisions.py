import csv
import re
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait


PAGE_URL = (
    "https://www.ed.gov/laws-and-policy/hearings-and-appeals/"
    "oha-judges-decisions-database"
)

FOLDER = Path(__file__).resolve().parent
DEBUG_FOLDER = FOLDER / "oha_debug"

# Locate the initialized decisions table and request all rows.
SHOW_ALL_SCRIPT = """
let tables = [];

if (
    window.jQuery &&
    window.jQuery.fn &&
    window.jQuery.fn.dataTable
) {
    tables = Array.from(window.jQuery.fn.dataTable.tables());
} else if (
    window.DataTable &&
    typeof window.DataTable.tables === "function"
) {
    tables = Array.from(window.DataTable.tables());
}

for (const table of tables) {
    let api;

    if (
        window.jQuery &&
        window.jQuery.fn &&
        window.jQuery.fn.dataTable
    ) {
        api = window.jQuery(table).DataTable();
    } else {
        api = new window.DataTable.Api(table);
    }

    const headings = Array.from(
        table.querySelectorAll("thead th, thead td")
    ).map(cell => cell.textContent).join(" ").toLowerCase();

    const sample = api.rows().nodes().toArray().slice(0, 10);
    const hasDockets = sample.some(row => {
        const cell = row.querySelector("td");
        return cell && /^\\d{2,4}-\\d+-/.test(
            cell.textContent.trim()
        );
    });

    if (
        !(headings.includes("docket") &&
          headings.includes("respondent")) &&
        !hasDockets
    ) {
        continue;
    }

    const settings = api.settings()[0];

    if (settings.oFeatures.bServerSide) {
        return {
            error: "This table uses server-side pagination. " +
                   "This script cannot confirm a full export."
        };
    }

    api.search("");
    api.columns().search("");
    api.page.len(-1).draw();

    const info = api.page.info();

    return {
        total: info.recordsTotal,
        html: api.rows({
            search: "none",
            page: "all"
        }).nodes().toArray().map(
            row => row.outerHTML
        ).join("")
    };
}

return null;
"""


def extract_records(html):
    soup = BeautifulSoup(
        "<table>" + html + "</table>",
        "html.parser",
    )

    records = []

    for index, row in enumerate(soup.find_all("tr"), start=1):
        cells = row.find_all(["td", "th"], recursive=False)

        # Do not silently discard malformed source rows.
        if len(cells) != 3:
            raise RuntimeError(
                f"Source row {index} has {len(cells)} columns "
                f"instead of 3. Row text: "
                f"{row.get_text(' ', strip=True)!r}"
            )

        docket = cells[0].get_text(" ", strip=True)
        respondent = cells[1].get_text(" ", strip=True)

        urls = []

        for link in cells[2].find_all("a", href=True):
            href = link["href"].strip()

            if not href or href.lower().startswith(
                ("#", "javascript:")
            ):
                continue

            urls.append(urljoin(PAGE_URL, href))

        # A single URL field cannot represent multiple links.
        # Stop rather than silently lose a document.
        if len(urls) > 1:
            raise RuntimeError(
                f"Source row {index}, docket {docket!r}, "
                f"contains multiple links: {urls}"
            )

        decision_url = urls[0] if urls else ""

        if (
            not re.match(r"^\d{2,4}-\d+-", docket)
            or not respondent
            or not decision_url
        ):
            print(
                f"REVIEW row {index}: "
                f"docket={docket!r}, "
                f"respondent={respondent!r}, "
                f"decision_url={decision_url!r}"
            )

        records.append({
            "Docket Number": docket,
            "Respondent": respondent,
            "View Decision": decision_url,
        })

    return records


def main():
    options = webdriver.ChromeOptions()
    options.add_argument("--window-size=1400,1000")

    driver = webdriver.Chrome(options=options)

    try:
        driver.get(PAGE_URL)
        print("Page title:", driver.title)
        print("Waiting for the initialized decisions table...")

        result = WebDriverWait(driver, 60).until(
            lambda browser: browser.execute_script(
                SHOW_ALL_SCRIPT
            )
        )

        if result.get("error"):
            raise RuntimeError(result["error"])

        expected = int(result["total"])

        if expected <= 0:
            raise RuntimeError(
                "The website reported no records."
            )

        records = extract_records(result["html"])

        print("Website total:", expected)
        print("Extracted records:", len(records))

        if len(records) != expected:
            raise RuntimeError(
                f"Count mismatch: expected {expected}, "
                f"extracted {len(records)}. "
                "No CSV was written."
            )

        output_path = FOLDER / "oha_judges_decisions.csv"

        with output_path.open(
            "w",
            newline="",
            encoding="utf-8-sig",
        ) as output:
            writer = csv.DictWriter(
                output,
                fieldnames=[
                    "Docket Number",
                    "Respondent",
                    "View Decision",
                ],
            )
            writer.writeheader()
            writer.writerows(records)

        print(f"\nSUCCESS: Exported {len(records)} records.")
        print("CSV saved to:", output_path)

    except Exception as error:
        print(f"\nFAILED: {type(error).__name__}: {error}")

        try:
            DEBUG_FOLDER.mkdir(exist_ok=True)

            (DEBUG_FOLDER / "page.html").write_text(
                driver.page_source,
                encoding="utf-8",
            )

            driver.save_screenshot(
                str(DEBUG_FOLDER / "page.png")
            )

            print("Diagnostics saved to:", DEBUG_FOLDER)
        except Exception:
            print("The browser was unavailable for diagnostics.")

        print(
            "Any CSV from a previous run is unchanged. "
            "Do not mistake it for a successful new export."
        )

    finally:
        driver.quit()


if __name__ == "__main__":
    main()
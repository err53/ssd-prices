import argparse
import io
from bs4 import BeautifulSoup
import cloudscraper
import pandas as pd
from thefuzz import fuzz
from thefuzz import process

scraper = cloudscraper.create_scraper()


def get_storage_prices(locale: str = "us"):
    url = f"https://diskprices.com/?locale={locale}"
    html = scraper.get(url).text

    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")

    records = []
    columns = []
    for tr in table.find_all("tr"):
        ths = tr.find_all("th")
        if ths != []:
            for each in ths:
                columns.append(each.text)
        else:
            trs = tr.find_all("td")
            record = []
            for each in trs:
                try:
                    link = each.find("a")["href"]
                    text = each.text
                    record.append(link)
                    record.append(text)
                except:  # noqa: E722
                    text = each.text
                    record.append(text)
            records.append(record)

    columns.insert(-1, "Link")

    return pd.DataFrame(records, columns=columns)


def get_storage_ratings():
    df = pd.read_csv(
        "https://docs.google.com/spreadsheets/d/"
        + "1B27_j9NDPU3cNlj2HKcrfpJKHkOf-Oi1DbuuQva2gT4"
        + "/export?gid=0&format=csv"
    )

    # drop where Brand or Model is NaN
    df = df.dropna(subset=["Brand", "Model"])

    return df


def save_dataframes():
    print("Saving dataframes to disk...")
    storage_prices = get_storage_prices(locale="ca")
    storage_ratings = get_storage_ratings()

    storage_prices.to_pickle("datasets/storage_prices.pkl")
    storage_ratings.to_pickle("datasets/storage_ratings.pkl")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--save", help="Save the dataframes to disk", action="store_true"
    )
    args = parser.parse_args()

    if args.save:
        save_dataframes()

    storage_prices = pd.read_pickle("datasets/storage_prices.pkl")
    storage_ratings = pd.read_pickle("datasets/storage_ratings.pkl")
    print(storage_prices)
    print(storage_ratings)

    # Replace non-breaking spaces in column names
    storage_prices.columns = storage_prices.columns.str.replace("\xa0", " ")

    # storage_prices preprocessing
    storage_prices = storage_prices[
        (~storage_prices["Capacity"].str.contains("x"))
        & (storage_prices["Form Factor"].isin(["M.2", "Internal"]))
        & (storage_prices["Technology"].isin(["NVMe", "SSD"]))
        & (storage_prices["Condition"] == "New")
    ]
    # rename Affiliate Link to Name
    storage_prices = storage_prices.rename(columns={"Affiliate Link": "Amazon Name"})
    # In name, replace substrings
    storage_prices["Amazon Name"] = storage_prices["Amazon Name"].str.replace(
        "TEAMGROUP", "Team"
    )
    print(storage_prices)

    # storage_ratings preprocessing
    # filter ratings for only M.2 drives
    storage_ratings = storage_ratings[storage_ratings["Form Factor"] == "M.2"]
    storage_ratings["Name"] = storage_ratings["Brand"] + " " + storage_ratings["Model"]
    print(storage_ratings)

    # merge storage_prices and storage_ratings using a fuzzy join with thefuzz
    for index, row in storage_prices.iterrows():
        match = process.extractOne(row["Amazon Name"], storage_ratings["Name"])
        if match:
            storage_prices.at[index, "Rating"] = match[1]
            storage_prices.at[index, "Model"] = match[0]
        else:
            storage_prices.at[index, "Rating"] = 0
            storage_prices.at[index, "Model"] = "Unknown"

    # save to csv
    storage_prices.to_csv("output/storage_prices.csv", index=False)

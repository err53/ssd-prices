import asyncio
import os
from bs4 import BeautifulSoup
import cloudscraper
import pandas as pd
import ssd_prices.gpt_fuzz as gpt_fuzz
import argparse
import termcolor

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


async def _main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--api-key",
        type=str,
        default=os.getenv("OPENAI_API_KEY"),
        required=bool(not os.getenv("OPENAI_API_KEY")),
        help="OpenAI API key",
    )
    parser.add_argument(
        "--categories",
        default=["Entry-Level NVMe", "Mid-Range NVMe", "High-End NVMe"],
        type=str,
        nargs="+",
        help="List of categories to filter by. Valid options (for now) are 'Entry-Level NVMe', 'Mid-Range NVMe', and 'High-End NVMe'",
    )

    args = parser.parse_args()
    gpt_fuzz.init_client(api_key=args.api_key)

    storage_prices = get_storage_prices(locale="ca")
    storage_ratings = get_storage_ratings()

    # Replace non-breaking spaces in column names
    storage_prices.columns = storage_prices.columns.str.replace("\xa0", " ")

    # storage_prices preprocessing
    storage_prices = storage_prices[
        (~storage_prices["Capacity"].str.contains("x"))
        & (storage_prices["Form Factor"].isin(["M.2"]))
        & (storage_prices["Technology"].isin(["NVMe"]))
        & (storage_prices["Condition"] == "New")
    ]
    # rename Affiliate Link to Name
    storage_prices = storage_prices.rename(columns={"Affiliate Link": "Amazon Name"})
    # In name, replace substrings
    storage_prices["Amazon Name"] = storage_prices["Amazon Name"].str.replace(
        "TEAMGROUP", "Team"
    )
    # In link, remove query parameters
    storage_prices["Link"] = storage_prices["Link"].str.split("?", expand=True)[0]
    # print(storage_prices)

    # storage_ratings preprocessing
    # filter ratings for only M.2 drives
    storage_ratings = storage_ratings[storage_ratings["Form Factor"] == "M.2"]
    storage_ratings["Name"] = storage_ratings["Brand"] + " " + storage_ratings["Model"]
    # print(storage_ratings)

    # generate Matches for storge ratings
    matches = storage_ratings["Name"].to_list()
    print(matches)

    async def match(row, index):
        mr = gpt_fuzz.MatchRequest(
            listing_name=row["Amazon Name"],
            possible_matches=storage_ratings["Name"].to_list(),
        )
        match = await gpt_fuzz.match_listing(mr)
        if match:
            storage_prices.at[index, "Product Name"] = match
            print(match)
        else:
            storage_prices.at[index, "Product Name"] = None

    await asyncio.gather(
        *[match(row, index) for index, row in storage_prices.iterrows()]
    )

    # merge storage_prices and storage_ratings
    storage_prices = storage_prices.merge(
        storage_ratings,
        how="left",
        left_on="Product Name",
        right_on="Name",
        suffixes=("", "_rating"),
    )

    # filter by categories
    storage_prices = storage_prices[storage_prices["Categories"].isin(args.categories)]

    # save to csv
    # os.makedirs("output", exist_ok=True)
    # storage_prices.to_csv("output/storage_prices.csv", index=False)

    colorized_prices = []
    for original in storage_prices["Price per TB"]:
        price = float(original.split("$")[1].replace(",", ""))
        if price <= 90:
            colorized_price = termcolor.colored(original, "green")
        elif price <= 110:
            colorized_price = termcolor.colored(original, "yellow")
        else:
            colorized_price = termcolor.colored(original, "red")
        colorized_prices.append(colorized_price)

    print_df = storage_prices.copy()
    print_df["Price per TB"] = colorized_prices
    print_df.columns = print_df.columns.str.replace(
        "Price per TB", termcolor.colored("Price per TB", "white")
    )

    print(
        print_df[
            [
                "Amazon Name",
                "Name",
                "Capacity",
                termcolor.colored("Price per TB", "white"),
                "Price",
                "Categories",
                "Link",
            ]
        ]
    )


def main():
    asyncio.run(_main())

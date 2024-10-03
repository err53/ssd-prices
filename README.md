# ssd-prices

Pull SSD prices from diskprices.com, categories from NewMaxx's SSD spreadsheet,
and use gpt-4o to accurately match the two together.

![preview](docs/image.png)

## Run

You'll need `rye` to run this for now, since I can't be bothered to build an executable.

Afterwards, run `rye sync` and `rye run ssd-priced`

## Future plans

- [ ] Find an effective fuzzy matcher / zero-shot classifier to avoid using gpt

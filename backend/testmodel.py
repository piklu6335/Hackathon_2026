from services.fake_news_model import predict_fake_news


tests = [
    "Donald Trump Sends Out Embarrassing New Year's Eve Message; This is Disturbing",
    "U.S. lawmakers question businessman at 2016 Trump Tower meeting: sources",
    "Trump administration issues new rules on U.S. visa waivers",
]


for text in tests:

    print("\n" + "=" * 80)

    print("TEXT:")
    print(text)

    result = predict_fake_news(
        text
    )

    print("\nRESULT:")
    print(result)
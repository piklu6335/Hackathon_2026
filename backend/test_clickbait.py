from services.clickbait_model import predict_clickbait


headlines = [
    "Government announces new education policy",
    "You Won't Believe What Happens Next!",
    "Scientists Reveal Shocking Secret About Your Brain",
    "New study examines the effects of sleep on memory",
    "This One Simple Trick Will Make You Rich",
    "Researchers publish findings from a ten-year study",
    "The Truth About This Popular Food Is Finally Revealed",
    "NASA announces new mission to study the Moon",
]


for headline in headlines:

    print("\n" + "=" * 80)

    result = predict_clickbait(
        headline
    )

    print(
        f"Headline: {headline}"
    )

    print(
        f"Score: {result['score']}"
    )

    print(
        f"Score: {result['score_percent']}%"
    )

    print(
        f"Level: {result['level']}"
    )
import pytest

@pytest.mark.asyncio
async def test_analyze_keyword_happy_path(amazon_agent, monkeypatch):
    # Arrange: ensure apify_client returns one product
    async def fake_scrape_amazon_products(keyword, max_products, client_id, price_min=None, price_max=None):
        return {
            "success": True,
            "products": [
                {
                    "title": "Scraped Product",
                    "price": 29.99,
                    "rating": 4.2,
                    "review_count": 45,
                    "asin": "BTEST2",
                    "url": "https://example.com/p2",
                    "image_url": "",
                    "brand": "BrandY",
                    "category": "Gadgets"
                }
            ]
        }

    # Patch the apify_client scrape function (app.apify_client was set in conftest)
    monkeypatch.setattr("app.apify_client.scrape_amazon_products", fake_scrape_amazon_products, raising=False)

    # Patch analyze_products to return a quick analyzed result (so we isolate keyword flow)
    async def fake_analyze_products(products, client_id=None):
        return {
            "status": "completed",
            "count": len(products),
            "saved_to_sheets": True,
            "products": [{"title": products[0].get("title", "x"), "price": products[0].get("price", 0), "score": 70, "recommendation": "Research"}],
            "insights": ["sample insight"]
        }
    monkeypatch.setattr(amazon_agent, "analyze_products", fake_analyze_products)

    # Act
    result = await amazon_agent.analyze_keyword(
        keyword="wireless headphones",
        client_id="client-123",
        max_products=10,
        investment=1500
    )

    # Assert expectations on returned structure
    assert result["status"] == "completed"
    assert result["client_id"] == "client-123"
    assert "search_keyword" in result and isinstance(result["search_keyword"], str)
    assert result["scraped"] == 1
    assert result["analyzed"] == 1
    assert result["saved_to_sheets"] is True or result.get("saved_to_sheets") is not None

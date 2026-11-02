import time
from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:5000/"
USERNAME = "ajay12"
PASSWORD = "ajay12"
TARGET_SHOP_NAME = "AJAY"

# 12 Multi-Photo Products to auto-publish under the "AJAY" Shop
PRODUCTS_TO_ADD = [
    {
        "title": "AJAY Pro Max Wireless Gaming Headset 7.1 Surround",
        "price": "1699",
        "mrp": "2999",
        "category": "Electronics",
        "images": "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?auto=format&fit=crop&w=700&q=80, https://images.unsplash.com/photo-1583394838336-acd977736f90?auto=format&fit=crop&w=700&q=80"
    },
    {
        "title": "AMOLED Smart Fitness Watch Bluetooth Calling",
        "price": "1999",
        "mrp": "3999",
        "category": "Electronics",
        "images": "https://images.unsplash.com/photo-1523275335684-37898b6baf30?auto=format&fit=crop&w=700&q=80, https://images.unsplash.com/photo-1546868871-7041f2a55e12?auto=format&fit=crop&w=700&q=80"
    },
    {
        "title": "RGB Honeycomb Ultra-Light Gaming Mouse 16000 DPI",
        "price": "899",
        "mrp": "1599",
        "category": "Electronics",
        "images": "https://images.unsplash.com/photo-1527814050087-3793815479db?auto=format&fit=crop&w=700&q=80, https://images.unsplash.com/photo-1615663245857-ac93bb7c39e7?auto=format&fit=crop&w=700&q=80"
    },
    {
        "title": "Portable Waterproof Bluetooth Party Speaker 40W",
        "price": "1499",
        "mrp": "2799",
        "category": "Electronics",
        "images": "https://images.unsplash.com/photo-1608043152269-423dbba4e7e1?auto=format&fit=crop&w=700&q=80"
    },
    {
        "title": "Classic Crisp White Oxford Button-Down Shirt",
        "price": "999",
        "mrp": "1799",
        "category": "Fashion",
        "images": "https://images.unsplash.com/photo-1596755094514-f87e34085b2c?auto=format&fit=crop&w=700&q=80, https://images.unsplash.com/photo-1602810318383-e386cc2a3ccf?auto=format&fit=crop&w=700&q=80"
    },
    {
        "title": "Dark Indigo Wide-Leg Streetwear Baggy Denim Jeans",
        "price": "1599",
        "mrp": "2699",
        "category": "Fashion",
        "images": "https://images.unsplash.com/photo-1542272604-787c3835535d?auto=format&fit=crop&w=700&q=80"
    },
    {
        "title": "Chunky Triple-White Low-Top Street Sneakers",
        "price": "1899",
        "mrp": "3299",
        "category": "Fashion",
        "images": "https://images.unsplash.com/photo-1549298916-b41d501d3772?auto=format&fit=crop&w=700&q=80, https://images.unsplash.com/photo-1600185365926-3a2ce3cdb9eb?auto=format&fit=crop&w=700&q=80"
    },
    {
        "title": "Oversized Graphic Fleece Streetwear Hoodie",
        "price": "1299",
        "mrp": "2299",
        "category": "Fashion",
        "images": "https://images.unsplash.com/photo-1556821840-3a63f95609a7?auto=format&fit=crop&w=700&q=80"
    },
    {
        "title": "Dual-Monitor Gas Spring Heavy Duty Desk Arm",
        "price": "2199",
        "mrp": "3899",
        "category": "Workspace",
        "images": "https://images.unsplash.com/photo-1593062096033-9a26b09da705?auto=format&fit=crop&w=700&q=80"
    },
    {
        "title": "8-in-1 Type-C PD 100W Aluminum Hub & 4K HDMI Dock",
        "price": "1399",
        "mrp": "2499",
        "category": "Workspace",
        "images": "https://images.unsplash.com/photo-1527864550417-7fd91fc51a46?auto=format&fit=crop&w=700&q=80"
    },
    {
        "title": "Extended XL Stitched Anti-Slip Desk Mat (900x400mm)",
        "price": "599",
        "mrp": "1199",
        "category": "Workspace",
        "images": "https://images.unsplash.com/photo-1618384887929-16ec33fab9ef?auto=format&fit=crop&w=700&q=80"
    },
    {
        "title": "Smart LED Monitor Light Bar Eye-Care Desk Lamp",
        "price": "1449",
        "mrp": "2599",
        "category": "SHOP_DEFAULT",
        "images": "https://images.unsplash.com/photo-1507473885765-e6ed057f782c?auto=format&fit=crop&w=700&q=80"
    }
]


def run_bulk_product_uploader():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=250)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        # Automatically accept all browser alert() popups
        page.on("dialog", lambda dialog: (print(f"🔔 Alert: {dialog.message}"), dialog.accept()))

        print(f"🌐 Opening {URL} ...")
        page.goto(URL)
        page.wait_for_selector("#userAccountBtn")

        # 1. Log in as ajay12
        print(f"🔑 Logging in as {USERNAME} ...")
        page.click("#userAccountBtn")
        page.wait_for_selector("#loginIdentifier", state="visible")
        page.fill("#loginIdentifier", USERNAME)
        page.fill("#loginPassword", PASSWORD)
        page.click("#signInForm button[type='submit']")

        # Wait for login modal to close
        page.wait_for_selector("#authModal.open", state="detached", timeout=10000)
        print("✅ Logged in successfully!")

        # 2. Loop through and publish all products to the AJAY shop
        for idx, item in enumerate(PRODUCTS_TO_ADD, start=1):
            print(f"📦 [{idx}/{len(PRODUCTS_TO_ADD)}] Publishing: {item['title']} ...")

            # Navigate to the Seller Hub tab
            page.click("#ptab-seller")
            page.wait_for_selector("#sellerStep2AddProductCard", state="visible", timeout=10000)

            # Ensure the "AJAY" shop is selected in #prodShopSelect
            shop_options = page.locator("#prodShopSelect option").all()
            for opt in shop_options:
                opt_text = opt.inner_text()
                if TARGET_SHOP_NAME.lower() in opt_text.lower():
                    val = opt.get_attribute("value")
                    page.select_option("#prodShopSelect", value=val)
                    break

            # Fill product fields
            page.fill("#prodTitle", item["title"])
            page.fill("#prodPrice", item["price"])
            page.fill("#prodMrp", item["mrp"])
            page.select_option("#prodCategorySelect", value=item["category"])
            page.fill("#prodImgUrl", item["images"])

            # Submit the product form
            page.click("#sellerStep2AddProductCard button[type='submit']")
            time.sleep(0.5)

        print("\n🎉 All products published to shop AJAY! Displaying the Shop Photo Grid...")
        time.sleep(5)
        browser.close()


if __name__ == "__main__":
    run_bulk_product_uploader()
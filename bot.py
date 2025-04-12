#!/usr/bin/env python
import os
import re
import logging
import requests
from bs4 import BeautifulSoup
from telegram import Update, ParseMode
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# Get bot token from environment variable or .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
if not TOKEN:
    raise ValueError("No TELEGRAM_BOT_TOKEN found in environment variables")

def start(update: Update, context: CallbackContext) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    update.message.reply_text(
        f'Hi {user.first_name}! Send me a Namshi product URL and I\'ll extract the product details for you.'
    )

def help_command(update: Update, context: CallbackContext) -> None:
    """Send a message when the command /help is issued."""
    update.message.reply_text(
        'Send me a Namshi product URL (e.g., https://www.namshi.com/uae-en/buy-product-name/product-id/p/) '
        'and I\'ll extract the product images, name, price, and available sizes for you.'
    )

def is_namshi_url(url: str) -> bool:
    """Check if the URL is a valid Namshi product URL."""
    return bool(re.match(r'https?://(?:www\.)?namshi\.com/.*?/p/', url))

def extract_product_info(url: str) -> dict:
    """Extract product information from a Namshi product URL."""
    # Clean the URL to remove tracking parameters
    clean_url = url.split('?')[0] if '?' in url else url
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9',
    }
    
    try:
        response = requests.get(clean_url, headers=headers)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract product name
        # First try to get it from the meta tags (more reliable)
        meta_title = soup.select_one('meta[property="og:title"]')
        if meta_title and 'content' in meta_title.attrs:
            name = meta_title['content'].split('|')[0].strip()
        else:
            # Try to find it in the HTML structure
            product_name = soup.select_one('h1.ProductConversion_productTitle__dvlc5')
            if not product_name:
                product_name = soup.select_one('h1[class*="productTitle"]')
            name = product_name.text.strip() if product_name else "Product name not found"
        
        # Extract product price
        price_element = soup.select_one('span.ProductPrice_value__hnFSS')
        if not price_element:
            price_element = soup.select_one('span[class*="value"]')
        price = price_element.text.strip() if price_element else "Price not found"
        
        # Extract available sizes
        sizes = []
        # Look for size buttons that are not disabled
        size_elements = soup.select('button.SizePills_size_variant__4qpXf:not([disabled])')
        if not size_elements:
            size_elements = soup.select('button[class*="size_variant"]:not([disabled])')
        
        for size_element in size_elements:
            sizes.append(size_element.text.strip())
        
        # Extract product images
        image_urls = []
        
        # First approach: Look for product gallery images
        gallery_images = soup.select('div.ImageGallery_imageContainer__jmn93 img')
        for img in gallery_images:
            if 'src' in img.attrs and img['src'].startswith('http'):
                image_url = img['src']
                # Ensure we're getting the highest resolution
                if 'width=' in image_url:
                    # Try to get a higher resolution by modifying the width parameter
                    image_url = image_url.split('width=')[0] + 'width=800'
                image_urls.append(image_url)
        
        # Second approach: Try to get images from meta tags if gallery approach failed
        if not image_urls:
            meta_images = soup.select('meta[property="og:image"]')
            for img in meta_images:
                if 'content' in img.attrs and img['content'].startswith('http') and 'namshi-logo' not in img['content'].lower():
                    # Filter out logo images and ensure it's a product image
                    if '/p/' in img['content'] or 'pzsku' in img['content']:
                        image_urls.append(img['content'])
        
        # Third approach: Look for product images in the HTML if other methods failed
        if not image_urls:
            # Look for images with specific product-related classes or attributes
            image_elements = soup.select('img[alt*="PUMA"], img[alt*="product"], img[alt*="Product"]')
            
            for img in image_elements:
                if 'src' in img.attrs and img['src'].startswith('http'):
                    image_url = img['src']
                    # Filter out small images, icons, and logos
                    if ('width=' in image_url and int(image_url.split('width=')[1].split('&')[0]) > 200) or \
                       ('/p/' in image_url or 'pzsku' in image_url):
                        # Ensure we're getting the highest resolution
                        if 'width=' in image_url:
                            image_url = image_url.split('width=')[0] + 'width=800'
                        image_urls.append(image_url)
        
        # Remove duplicates while preserving order
        image_urls = list(dict.fromkeys(image_urls))
        
        # Additional filtering to remove non-product images
        filtered_urls = []
        for url in image_urls:
            # Include only URLs that are likely to be product images
            if any(pattern in url.lower() for pattern in ['/p/', 'pzsku', 'product', '/pzsku/']):
                filtered_urls.append(url)
        
        # If we filtered out all images, revert to the original list
        image_urls = filtered_urls if filtered_urls else image_urls
        
        return {
            'name': name,
            'price': price,
            'sizes': sizes,
            'image_urls': image_urls
        }
    except Exception as e:
        logger.error(f"Error extracting product info: {e}")
        return {
            'name': "Error extracting product name",
            'price': "Error extracting price",
            'sizes': [],
            'image_urls': []
        }

def download_image(url: str) -> bytes:
    """Download an image from a URL."""
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.content
    except Exception as e:
        logger.error(f"Error downloading image: {e}")
        return None

def handle_message(update: Update, context: CallbackContext) -> None:
    """Process the user message."""
    message_text = update.message.text
    
    # Check if the message contains a Namshi URL
    if is_namshi_url(message_text):
        # Inform user that processing has started
        processing_msg = update.message.reply_text("Processing your Namshi product URL... Please wait.")
        
        # Extract product information
        product_info = extract_product_info(message_text)
        
        # Prepare product details text
        sizes_text = ", ".join(product_info['sizes']) if product_info['sizes'] else "No sizes available"
        details_text = (
            f"*{product_info['name']}*\n\n"
            f"*Price:* {product_info['price']}\n\n"
            f"*Available Sizes:* {sizes_text}"
        )
        
        # Import necessary classes
        from telegram import InputMediaPhoto
        
        # Send product images as a media group with caption
        if product_info['image_urls']:
            # Download all images first
            media_group = []
            for i, image_url in enumerate(product_info['image_urls']):
                image_data = download_image(image_url)
                if image_data:
                    # Add caption to the first image only
                    caption = details_text if i == 0 else ""
                    parse_mode = ParseMode.MARKDOWN if i == 0 else None
                    
                    # Create InputMediaPhoto object
                    media_photo = InputMediaPhoto(
                        media=image_data,
                        caption=caption,
                        parse_mode=parse_mode
                    )
                    media_group.append(media_photo)
            
            if media_group:
                # Send media group (up to 10 images per group as per Telegram's limit)
                if len(media_group) <= 10:
                    context.bot.send_media_group(
                        chat_id=update.effective_chat.id,
                        media=media_group
                    )
                else:
                    # If more than 10 images, send in batches
                    for i in range(0, len(media_group), 10):
                        batch = media_group[i:i+10]
                        context.bot.send_media_group(
                            chat_id=update.effective_chat.id,
                            media=batch
                        )
                
                update.message.reply_text("All product information has been sent!")
            else:
                # If no images were successfully downloaded
                update.message.reply_text(details_text, parse_mode=ParseMode.MARKDOWN)
                update.message.reply_text("Failed to download product images.")
        else:
            # If no image URLs were found
            update.message.reply_text(details_text, parse_mode=ParseMode.MARKDOWN)
            update.message.reply_text("No product images found.")
        
        # Delete the processing message
        context.bot.delete_message(
            chat_id=processing_msg.chat_id,
            message_id=processing_msg.message_id
        )
    else:
        update.message.reply_text(
            "Please send a valid Namshi product URL (e.g., https://www.namshi.com/uae-en/buy-product-name/product-id/p/)"
        )

def main() -> None:
    """Start the bot."""
    # Create the Updater and pass it your bot's token
    updater = Updater(TOKEN, use_context=True)

    # Get the dispatcher to register handlers
    dispatcher = updater.dispatcher

    # Register command handlers
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("help", help_command))

    # Register message handler
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

    # Start the Bot with a longer timeout
    updater.start_polling(timeout=30, drop_pending_updates=True)
    updater.idle()

if __name__ == '__main__':
    main()

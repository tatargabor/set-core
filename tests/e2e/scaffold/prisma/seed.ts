import { PrismaClient } from "@prisma/client";

const prisma = new PrismaClient();

async function main() {
  const products = [
    {
      name: "Laptop",
      description: "High-performance laptop for work and gaming",
      price: 129999,
      stock: 15,
      imageUrl: "https://placehold.co/400x300?text=Laptop",
    },
    {
      name: "Gaming Mouse",
      description: "Ergonomic gaming mouse with RGB lighting",
      price: 4999,
      stock: 50,
      imageUrl: "https://placehold.co/400x300?text=Mouse",
    },
    {
      name: "Mechanical Keyboard",
      description: "Cherry MX mechanical keyboard with backlight",
      price: 8999,
      stock: 30,
      imageUrl: "https://placehold.co/400x300?text=Keyboard",
    },
    {
      name: "Monitor",
      description: '27" 4K IPS monitor with wide color gamut',
      price: 44999,
      stock: 10,
      imageUrl: "https://placehold.co/400x300?text=Monitor",
    },
    {
      name: "Webcam",
      description: "1080p webcam with built-in microphone",
      price: 5999,
      stock: 40,
      imageUrl: "https://placehold.co/400x300?text=Webcam",
    },
    {
      name: "USB-C Hub",
      description: "7-in-1 USB-C hub with HDMI, USB 3.0, SD card",
      price: 3499,
      stock: 60,
      imageUrl: "https://placehold.co/400x300?text=USB-C+Hub",
    },
  ];

  for (const product of products) {
    await prisma.product.upsert({
      where: { id: products.indexOf(product) + 1 },
      update: product,
      create: product,
    });
  }

  console.log(`Seeded ${products.length} products`);
}

main()
  .then(async () => {
    await prisma.$disconnect();
  })
  .catch(async (e) => {
    console.error(e);
    await prisma.$disconnect();
    process.exit(1);
  });

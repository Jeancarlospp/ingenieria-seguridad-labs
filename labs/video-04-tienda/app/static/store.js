const checkout = document.getElementById("checkout-form");
if (checkout) {
  checkout.addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = document.getElementById("confirm-order");
    const error = document.getElementById("checkout-error");
    button.disabled = true;
    error.hidden = true;
    const data = {
      product_id: Number(checkout.dataset.product),
      quantity: Number(checkout.dataset.quantity),
      unit_price: Number(checkout.dataset.price),
      customer_name: checkout.elements.customer_name.value.trim(),
      customer_email: checkout.elements.customer_email.value.trim(),
    };
    try {
      const response = await fetch(checkout.dataset.endpoint, {
        method: "POST",
        headers: {"Content-Type": "application/json", "X-CSRF-Token": checkout.elements.csrf_token.value},
        body: JSON.stringify(data),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || "No pudimos confirmar el pedido.");
      window.location.assign(result.order_url);
    } catch (reason) {
      error.textContent = reason.message || "Revisa tu conexión e inténtalo de nuevo.";
      error.hidden = false;
      button.disabled = false;
    }
  });
}

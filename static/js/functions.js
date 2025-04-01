document.addEventListener("DOMContentLoaded", function () {
  const inicioBtn = document.querySelector("#inicio-btn");
  const cardsContainer = document.querySelector("#container-cards");
  const burgerMenu = document.querySelector(".burger-menu");
  const menu = document.querySelector(".menu");
  // Toggle password visibility on click
  const passwordBtn = document.querySelectorAll(".toggle-btn");
  const passwordInput = document.querySelectorAll(".passwd-field");
  const passwordIcon = document.querySelectorAll(".toggle-btn i");
  passwordBtn.forEach((btn, index) => {
    btn.addEventListener("click", () => {
      togglePasswordVisibility(passwordInput[index], passwordIcon[index]);
    });
  });

  // Scroll to cards section
  inicioBtn.addEventListener("click", () => {
    cardsContainer.scrollIntoView({ behavior: "smooth" });
  });
  // Toggle menu for responsive design
  burgerMenu.addEventListener("click", () => {
    menu.classList.toggle("active");
  });
});

// Toggle password visibility on click
function togglePasswordVisibility(passwordInput, passwordIcon) {
  if (passwordInput.type === "password") {
    passwordInput.type = "text";
    passwordIcon.classList.remove("fa-eye-slash");
    passwordIcon.classList.add("fa-eye");
  } else {
    passwordInput.type = "password";
    passwordIcon.classList.remove("fa-eye");
    passwordIcon.classList.add("fa-eye-slash");
  }
}

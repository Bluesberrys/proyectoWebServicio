
let tiempoInicio = Date.now(); 
let tiempoTotal = 0;

document.addEventListener("DOMContentLoaded", function () {
  const inicioBtn = document.querySelector("#inicio-btn");
  const burgerMenu = document.querySelector(".burger-menu");

  if (inicioBtn) {
      inicioBtn.addEventListener("click", () => {
          const cardsContainer = document.querySelector("#container-cards");
          if (cardsContainer) {
              cardsContainer.scrollIntoView({ behavior: "smooth" });
          }
      });
  }

  if (burgerMenu) {
      burgerMenu.addEventListener("click", () => {
          const headerMenu = document.querySelector(".menu");
          if (headerMenu) {
              headerMenu.classList.toggle("active");
          }
      });
  }
});

document.addEventListener("DOMContentLoaded", function () {
  const form = document.querySelector("form[action='/actualizar_rol']");
  form.addEventListener("submit", async function (event) {
      event.preventDefault();

      const formData = new FormData(form);
      const response = await fetch("/actualizar_rol", {
          method: "POST",
          body: formData
      });

      const data = await response.json();

      if (data.success) {
          alert("Rol actualizado a: " + data.nuevo_rol);
          location.reload();
      } else {
          alert("Error al actualizar el rol");
      }
  });
});


function registrarTiempo(usuarioId, tiempo) {
  fetch('/api/registrar_tiempo', {
      method: 'POST',
      headers: {
          'Content-Type': 'application/json'
      },
      body: JSON.stringify({
          usuario_id: usuarioId,
          tiempo: tiempo
      })
  })
  .then(response => {
      if (!response.ok) {
          throw new Error('Error en la respuesta de la API');
      }
      return response.json();
  })
  .then(data => {
      if (data.success) {
          console.log('Tiempo registrado exitosamente');
      } else {
          console.error('Error al registrar tiempo:', data.error);
      }
  })
  .catch(error => console.error('Error en la solicitud:', error));
}


window.addEventListener('beforeunload', function() {
    let tiempoFin = Date.now(); 
    tiempoTotal = Math.round((tiempoFin - tiempoInicio) / 1000); 
    const usuarioId = 20; 


    registrarTiempo(usuarioId, tiempoTotal);
});
function toggleDropdown(event) {
    event.preventDefault();
    document.getElementById("dropdownMenu").classList.toggle("show");
  }

  window.addEventListener("click", function(e) {
    const dropdown = document.querySelector(".dropdown");
    const menu = document.getElementById("dropdownMenu");
    if (!dropdown.contains(e.target)) {
      menu.classList.remove("show");
    }
  });
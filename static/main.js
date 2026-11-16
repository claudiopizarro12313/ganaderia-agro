// Confirmación antes de acciones que borran datos: <form data-confirmar="mensaje">
document.addEventListener('submit', (e) => {
    const mensaje = e.target.dataset.confirmar;
    if (mensaje && !confirm(mensaje)) {
        e.preventDefault();
    }
});

// En Finanzas, las categorías cambian según sea Ingreso o Gasto
const tipo = document.getElementById('tipo');
const categoria = document.getElementById('categoria');
if (tipo && categoria) {
    const categorias = JSON.parse(tipo.dataset.categorias);
    const llenar = () => {
        categoria.innerHTML = '';
        (categorias[tipo.value] || []).forEach((nombre) => {
            const opcion = document.createElement('option');
            opcion.value = nombre;
            opcion.textContent = nombre;
            categoria.appendChild(opcion);
        });
    };
    tipo.addEventListener('change', llenar);
    llenar();
}

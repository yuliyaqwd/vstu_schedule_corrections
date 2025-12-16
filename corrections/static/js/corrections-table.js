// Сортировка таблицы
document.querySelectorAll('th[data-sort]').forEach(th => {
    th.addEventListener('click', () => {
        const sortBy = th.dataset.sort;
        // Логика сортировки через AJAX
        loadCorrections({sort_by: sortBy});
    });
});

// Фильтрация
document.getElementById('apply-filters').addEventListener('click', () => {
    const statuses = Array.from(document.getElementById('status-filter').selectedOptions)
        .map(opt => opt.value);
    
    loadCorrections({status: statuses});
});

// Загрузка корректировок через AJAX
async function loadCorrections(params = {}) {
    const queryString = new URLSearchParams(params).toString();
    const response = await fetch(`/corrections/api/corrections/?${queryString}`);
    const data = await response.json();
    
    // Обновление таблицы
    updateTable(data.corrections);
}
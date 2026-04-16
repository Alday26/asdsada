const regionSelect = document.getElementById('region');
const provinceSelect = document.getElementById('province');
const barangaySelect = document.getElementById('barangay');

// Sample address data (you can expand this later)
const addressData = {
  "NCR": {
    "Metro Manila": ["Barangay 1", "Barangay 2", "Barangay 3"]
  },
  "Region IV-A": {
    "Cavite": ["Bacoor", "Dasmariñas", "Imus"],
    "Laguna": ["Calamba", "San Pablo", "Santa Rosa"]
  },
  "Region III": {
    "Pampanga": ["Angeles", "San Fernando", "Mabalacat"]
  }
};

// Populate regions
for (let region in addressData) {
  let option = document.createElement('option');
  option.value = region;
  option.textContent = region;
  regionSelect.appendChild(option);
}

// When region changes
regionSelect.addEventListener('change', function() {
  provinceSelect.innerHTML = '<option value="">Select Province</option>';
  barangaySelect.innerHTML = '<option value="">Select Barangay</option>';
  let provinces = addressData[this.value];
  if (provinces) {
    for (let province in provinces) {
      let option = document.createElement('option');
      option.value = province;
      option.textContent = province;
      provinceSelect.appendChild(option);
    }
  }
});

// When province changes
provinceSelect.addEventListener('change', function() {
  barangaySelect.innerHTML = '<option value="">Select Barangay</option>';
  let barangays = addressData[regionSelect.value][this.value];
  if (barangays) {
    barangays.forEach(b => {
      let option = document.createElement('option');
      option.value = b;
      option.textContent = b;
      barangaySelect.appendChild(option);
    });
  }
});

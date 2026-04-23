window.PetProfileSync = (function () {
    function getStorageKey(username) {
        return `pet_profile_${username}`;
    }

    function normalizeProfile(rawProfile) {
        const data = rawProfile || {};
        return {
            pet_name: data.pet_name || "",
            pet_gender: data.pet_gender || "unknown",
            pet_type: data.pet_type || "dog",
            age_stage: data.age_stage || "adult",
            weight: data.weight || "",
            bcs: data.bcs || "normal",
            sterilized: data.sterilized || "unknown",
            profile_notes: data.profile_notes || "",
            updated_at: data.updated_at || ""
        };
    }

    function getProfile(username) {
        if (!username) return normalizeProfile({});

        const direct = localStorage.getItem(getStorageKey(username));
        if (direct) {
            try {
                return normalizeProfile(JSON.parse(direct));
            } catch (e) {}
        }

        const assessmentDraft = localStorage.getItem(`assessment_basic_${username}`);
        if (assessmentDraft) {
            try {
                return normalizeProfile(JSON.parse(assessmentDraft));
            } catch (e) {}
        }

        return normalizeProfile({});
    }

    function saveProfile(username, profile) {
        if (!username) return;
        const normalized = normalizeProfile(profile);
        localStorage.setItem(getStorageKey(username), JSON.stringify(normalized));
        localStorage.setItem(`assessment_basic_${username}`, JSON.stringify(normalized));
        return normalized;
    }

    function saveFromDashboard(username, basicInfo) {
        if (!username || !basicInfo) return;
        const oldProfile = getProfile(username);
        const merged = {
            ...oldProfile,
            pet_type: basicInfo.pet_type || oldProfile.pet_type,
            age_stage: basicInfo.age_stage || oldProfile.age_stage,
            weight: basicInfo.weight || oldProfile.weight,
            bcs: basicInfo.bcs || oldProfile.bcs,
            updated_at: new Date().toLocaleString()
        };
        saveProfile(username, merged);
    }

    function fillDashboardForm(username) {
        const profile = getProfile(username);
        const mapping = {
            pet_type: "pet_type",
            age_stage: "age_stage",
            weight: "weight",
            bcs: "bcs"
        };

        Object.entries(mapping).forEach(([key, elementId]) => {
            const el = document.getElementById(elementId);
            if (el && profile[key] !== undefined && profile[key] !== "") {
                el.value = profile[key];
            }
        });
    }

    return {
        getProfile,
        saveProfile,
        saveFromDashboard,
        fillDashboardForm
    };
})();

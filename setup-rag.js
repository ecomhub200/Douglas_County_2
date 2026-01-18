// =====================================================
// DOMAIN KNOWLEDGE RAG SETUP
// Copy and paste this entire block into browser console
// =====================================================

(async function setupDomainKnowledge() {
    console.log('🚀 Setting up Domain Knowledge RAG...\n');

    // Step 1: Test Voyage AI
    console.log('Step 1/4: Testing Voyage AI...');
    try {
        const embedding = await voyageEmbedQuery('test');
        console.log('✅ Voyage AI connected! Dimensions:', embedding.length);
    } catch (e) {
        console.error('❌ Voyage AI failed:', e.message);
        return;
    }

    // Step 2: Check/Create Qdrant collection
    console.log('\nStep 2/4: Setting up Qdrant collection...');
    try {
        let info = await qdrantGetCollectionInfo();
        if (info) {
            console.log('✅ Collection exists with', info.points_count, 'points');
        } else {
            console.log('Creating collection...');
            await qdrantCreateCollection(1024);
            console.log('✅ Collection created!');
        }
    } catch (e) {
        console.error('❌ Qdrant setup failed:', e.message);
        return;
    }

    // Step 3: Index sample documents
    console.log('\nStep 3/4: Indexing sample documents...');
    try {
        await indexSampleDocuments();
        console.log('✅ Sample documents indexed!');
    } catch (e) {
        console.error('❌ Indexing failed:', e.message);
        return;
    }

    // Step 4: Test search
    console.log('\nStep 4/4: Testing search...');
    try {
        const results = await ragSearch('signal warrant crash experience', [], 3);
        console.log('✅ Search works! Found', results.length, 'results:');
        results.forEach(function(r, i) {
            console.log('   ' + (i+1) + '. [' + r.source + '] ' + r.section + ' - ' + r.title + ' (score: ' + r.score.toFixed(3) + ')');
        });
    } catch (e) {
        console.error('❌ Search failed:', e.message);
        return;
    }

    console.log('\n🎉 Setup complete! You can now use the Domain Knowledge tab.');
    console.log('Try asking: "What is the signal warrant for crash experience?"');

    showNotification('Domain Knowledge RAG setup complete!', 'success');
})();

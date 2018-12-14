const Datastore = require('@google-cloud/datastore');
/**
 * Triggered from a message on a Cloud Pub/Sub topic.
 *
 * @param {!Object} event The Cloud Functions event.
 * @param {!Function} The callback function.
 */
exports.subscribe = function subscribe(event, callback) {
  const pubsubMessage = event.data;
  const datastore = Datastore({
    projectId: 'smartrise-221512'
  });
  const data = JSON.parse(Buffer.from(pubsubMessage.data, 'base64').toString());
  data.timestamp = new Date(data.timestamp)
  
  const entity = {
    'key': datastore.key(['locations', event.eventId]),
    'data': data
    };

  datastore.save(entity)
  	//.then(() => { console.log(entity) })
    .catch((err) => {
      console.error('ERROR:', err);
    });

  callback();
};
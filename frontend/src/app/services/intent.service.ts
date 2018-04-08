import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { environment } from '../../environments/environment';

@Injectable()
export class IntentService {
  public static storyTypes = {
    'mobile': 'Mobile number',
    'email': 'Email',
    'free_text': 'Free Text',
    'number': 'Number',
    'list': 'List',
  };

  constructor(public http: HttpClient) {
  }

  getStories() {
    return this.http.get(environment.ikyBackend + 'stories/').toPromise();
  }

  getStory(id) {
    return this.http.get(environment.ikyBackend + `stories/${id}`).toPromise();
  }

  saveStory(story) {
    if (story._id) {
      return this.update_story(story);
    } else {
      delete story._id;
      return this.create_story(story);
    }
  }

  create_story(story) {
    return this.http.post(environment.ikyBackend + `stories/`, story).toPromise();
  }

  update_story(story) {
    return this.http.put(environment.ikyBackend + `stories/${story._id}`, story).toPromise();
  }

  delete_story(id) {
    return this.http.delete(environment.ikyBackend + `stories/${id}`, {}).toPromise();
  }

  importStories(fileToUpload: File){
    const formData: FormData = new FormData();
    formData.append('file', fileToUpload, fileToUpload.name);
    return this.http
      .post(environment.ikyBackend +"stories/import", formData).toPromise();
  }

}

